from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (ORDEM_CORES, Consumivel, Impressora, ModeloImpressora, ModeloToner,
                     NivelToner, Pedido, Reposicao, Troca)
from .niveis import DIAS_DESATUALIZADO, RESERVA_IDEAL

STATUS_EM_ANDAMENTO = ('pendente', 'enviado')


def impressoras_com_niveis():
    """Impressoras com níveis por cor e o nome do toner de cada cor já anexados."""
    impressoras = list(
        Impressora.objects.select_related('modelo', 'modelo__caixa_residuo')
        .prefetch_related('modelo__toners__consumivel', 'niveis')
        .order_by('localizacao', 'nome')
    )
    limite = timezone.now() - timedelta(days=DIAS_DESATUALIZADO)
    for imp in impressoras:
        toner_da_cor = {t.cor: t.consumivel for t in imp.modelo.toners.all()}
        imp.colorida = len(toner_da_cor) > 1
        imp.linhas = imp.niveis_ordenados()
        for linha in imp.linhas:
            linha.toner = toner_da_cor.get(linha.cor)
        imp.sem_reserva_sala = any(l.na_sala == 0 for l in imp.linhas)
        imp.nivel_minimo = min((l.nivel for l in imp.linhas), default=100)
        # a cor conferida há mais tempo define o "atualizado em" do card
        imp.atualizado_em_nivel = min((l.atualizado_em for l in imp.linhas), default=None)
        imp.desatualizada = bool(imp.atualizado_em_nivel and imp.atualizado_em_nivel < limite)
    return impressoras


def calcular_alertas(impressoras=None):
    """Itens com estoque abaixo do mínimo e ao menos uma impressora sem reserva na sala."""
    sem_reserva = defaultdict(list)  # consumivel_id -> nomes das impressoras (e cor) sem reserva
    for imp in (impressoras if impressoras is not None else impressoras_com_niveis()):
        for linha in imp.linhas:
            if linha.toner and linha.na_sala == 0:
                rotulo = f'{imp.nome} ({linha.get_cor_display()})' if imp.colorida else imp.nome
                sem_reserva[linha.toner.id].append(rotulo)
        residuo = imp.modelo.caixa_residuo
        if residuo and imp.residuo_na_sala == 0:
            sem_reserva[residuo.id].append(imp.nome)

    em_andamento = set(
        Pedido.objects.filter(status__in=STATUS_EM_ANDAMENTO)
        .values_list('consumivel_id', flat=True)
    )

    alertas = []
    for item in Consumivel.objects.order_by('tipo', 'nome'):
        if item.estoque_unidade >= item.estoque_minimo or not sem_reserva[item.id]:
            continue
        alertas.append({
            'consumivel': item,
            'afetadas': sem_reserva[item.id],
            'quantidade_sugerida': max(item.estoque_minimo - item.estoque_unidade, 1),
            'em_andamento': item.id in em_andamento,
        })
    return alertas


@transaction.atomic
def mudar_status_pedido(pedido_id, novo_status):
    """Atualiza o status; ao passar para 'recebido' soma no estoque (uma única vez)."""
    pedido = Pedido.objects.select_for_update().select_related('consumivel').get(pk=pedido_id)
    if pedido.status == 'recebido' or novo_status == pedido.status:
        return pedido

    pedido.status = novo_status
    pedido.save(update_fields=['status'])

    if novo_status == 'recebido':
        consumivel = pedido.consumivel
        consumivel.estoque_unidade += pedido.quantidade
        consumivel.save(update_fields=['estoque_unidade'])
    return pedido


@transaction.atomic
def criar_modelo(nome, colorida, usa_residuo, estoque_minimo):
    """Cria o modelo com os toners de cada cor (e a caixa de resíduo) já ligados e com estoque 0."""
    residuo = None
    if usa_residuo:
        residuo = Consumivel.objects.create(nome=f'{nome} - Caixa de resíduo', tipo='residuo',
                                            estoque_minimo=estoque_minimo)
    modelo = ModeloImpressora.objects.create(
        nome=nome, tipo='laser colorida' if colorida else 'laser mono', caixa_residuo=residuo)
    for cor in (ORDEM_CORES if colorida else ['preto']):
        toner = Consumivel.objects.create(nome=f'{nome} - Toner {cor.capitalize()}', tipo='toner',
                                          estoque_minimo=estoque_minimo)
        ModeloToner.objects.create(modelo=modelo, cor=cor, consumivel=toner)
    return modelo


class SemReserva(Exception):
    """Não há toner reserva na sala para fazer a troca."""


class SemEstoque(Exception):
    """O estoque da unidade não tem a quantidade necessária."""

    def __init__(self, item):
        super().__init__(item.nome)
        self.item = item


def _nome_do_usuario(usuario):
    if not usuario.is_authenticated:
        return ''
    return usuario.get_full_name() or usuario.get_username()


def _toner_do_modelo(impressora, cor):
    ligacao = (ModeloToner.objects.filter(modelo=impressora.modelo, cor=cor).first())
    return Consumivel.objects.select_for_update().get(pk=ligacao.consumivel_id) if ligacao else None


@transaction.atomic
def trocar_toner(impressora_id, cor, usuario, origem='sala'):
    """Troca de toner: o nível volta a 100% e o toner novo sai da reserva da sala ou do estoque."""
    nivel = (NivelToner.objects.select_for_update()
             .select_related('impressora__modelo').get(impressora_id=impressora_id, cor=cor))
    impressora = nivel.impressora
    toner = _toner_do_modelo(impressora, cor)

    if origem == 'estoque':
        if toner is None or toner.estoque_unidade < 1:
            raise SemEstoque(toner or Consumivel(nome=f'toner {cor}'))
        toner.estoque_unidade -= 1
        toner.save(update_fields=['estoque_unidade'])
    else:
        origem = 'sala'
        if nivel.na_sala < 1:
            raise SemReserva
        nivel.na_sala -= 1

    troca = Troca.objects.create(
        impressora=impressora, impressora_nome=impressora.nome, cor=cor,
        toner=toner, toner_nome=toner.nome if toner else '', nivel_anterior=nivel.nivel,
        origem=origem, usuario=usuario if usuario.is_authenticated else None,
        usuario_nome=_nome_do_usuario(usuario))
    nivel.nivel = 100
    nivel.save(update_fields=['na_sala', 'nivel'])
    return troca


def salas_para_reabastecer(impressoras=None):
    """Toners (por cor) e caixas de resíduo cuja reserva na sala está abaixo da ideal."""
    linhas = []
    for imp in (impressoras if impressoras is not None else impressoras_com_niveis()):
        for l in imp.linhas:
            if l.toner and l.na_sala < RESERVA_IDEAL:
                linhas.append({'impressora': imp, 'tipo': 'toner', 'cor': l.cor,
                               'cor_nome': l.get_cor_display(), 'item': l.toner,
                               'falta': RESERVA_IDEAL - l.na_sala, 'chave': l.cor})
        residuo = imp.modelo.caixa_residuo
        if residuo and imp.residuo_na_sala < RESERVA_IDEAL:
            linhas.append({'impressora': imp, 'tipo': 'residuo', 'cor': '', 'cor_nome': '',
                           'item': residuo, 'falta': RESERVA_IDEAL - imp.residuo_na_sala,
                           'chave': 'residuo'})
    for linha in linhas:
        linha['cobre'] = linha['item'].estoque_unidade >= linha['falta']
    return linhas


@transaction.atomic
def repor_na_sala(impressora_id, chave, usuario):
    """Passa do estoque da unidade para a reserva da sala o que falta para chegar à reserva ideal.

    `chave` é a cor do toner ou 'residuo'. Levanta SemEstoque se o estoque não cobre."""
    impressora = Impressora.objects.select_for_update().select_related(
        'modelo', 'modelo__caixa_residuo').get(pk=impressora_id)
    if chave == 'residuo':
        item, atual, cor = impressora.modelo.caixa_residuo, impressora.residuo_na_sala, ''
        nivel = None
    else:
        nivel = NivelToner.objects.select_for_update().get(impressora=impressora, cor=chave)
        item, atual, cor = _toner_do_modelo(impressora, chave), nivel.na_sala, chave
    if item is None:
        raise ValueError('Este item não está ligado ao modelo.')
    quantidade = RESERVA_IDEAL - atual
    if quantidade < 1:
        return None  # já tem a reserva ideal
    item = Consumivel.objects.select_for_update().get(pk=item.pk)
    if item.estoque_unidade < quantidade:
        raise SemEstoque(item)

    item.estoque_unidade -= quantidade
    item.save(update_fields=['estoque_unidade'])
    if nivel is None:
        impressora.residuo_na_sala += quantidade
        impressora.save(update_fields=['residuo_na_sala'])
    else:
        nivel.na_sala += quantidade
        nivel.save(update_fields=['na_sala'])
    return Reposicao.objects.create(
        impressora=impressora, impressora_nome=impressora.nome, cor=cor, item=item,
        item_nome=item.nome, quantidade=quantidade,
        usuario=usuario if usuario.is_authenticated else None,
        usuario_nome=_nome_do_usuario(usuario))


def repor_tudo(usuario):
    """Repõe tudo o que o estoque alcança; o que não alcança fica na lista. Retorna (feitas, sem_estoque)."""
    feitas, sem_estoque = [], []
    for linha in salas_para_reabastecer():
        try:
            reposicao = repor_na_sala(linha['impressora'].id, linha['chave'], usuario)
        except SemEstoque:
            sem_estoque.append(linha)
        else:
            if reposicao:
                feitas.append(reposicao)
    return feitas, sem_estoque
