from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (ORDEM_CORES, AjusteEstoque, AjusteReserva, Consumivel, Impressora,
                     ModeloImpressora, ModeloToner, NivelToner, Pedido, Reposicao, Troca)
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
    """Itens para pedir: estoque abaixo do mínimo ("Pouco") ou que não dá para repor as salas.

    A quantidade sugerida cobre a reposição das salas e ainda deixa o mínimo no estoque,
    descontando o que já foi pedido e ainda não chegou."""
    sem_reserva = defaultdict(list)  # consumivel_id -> nomes das impressoras (e cor) sem reserva
    falta_nas_salas = defaultdict(int)  # consumivel_id -> quanto falta para a reserva ideal
    for imp in (impressoras if impressoras is not None else impressoras_com_niveis()):
        for linha in imp.linhas:
            if linha.toner and linha.na_sala < RESERVA_IDEAL:
                falta_nas_salas[linha.toner.id] += RESERVA_IDEAL - linha.na_sala
            if linha.toner and linha.na_sala == 0:  # o item já é o toner da cor: basta a impressora
                sem_reserva[linha.toner.id].append(imp.nome)
        residuo = imp.modelo.caixa_residuo
        if residuo and imp.residuo_na_sala < RESERVA_IDEAL:
            falta_nas_salas[residuo.id] += RESERVA_IDEAL - imp.residuo_na_sala
        if residuo and imp.residuo_na_sala == 0:
            sem_reserva[residuo.id].append(imp.nome)

    ja_pedido = dict(
        Pedido.objects.filter(status__in=STATUS_EM_ANDAMENTO)
        .values('consumivel_id').annotate(total=Sum('quantidade'))
        .values_list('consumivel_id', 'total')
    )

    alertas = []
    for item in Consumivel.objects.order_by('tipo', 'nome'):
        falta = falta_nas_salas[item.id]
        pouco = item.estoque_unidade < item.estoque_minimo
        nao_cobre_as_salas = falta > item.estoque_unidade
        if not pouco and not nao_cobre_as_salas:
            continue
        necessario = item.estoque_minimo + falta - item.estoque_unidade
        pedido = ja_pedido.get(item.id, 0)
        alertas.append({
            'consumivel': item,
            'afetadas': sem_reserva[item.id],
            'falta_nas_salas': falta,
            'quantidade_sugerida': max(necessario - pedido, 1),
            'ja_pedido': pedido,
            'em_andamento': pedido > 0,
            'pedido_cobre': pedido > 0 and pedido >= necessario,
        })
    return alertas


@transaction.atomic
def mudar_status_pedido(pedido_id, novo_status, usuario=None):
    """Atualiza o status; ao passar para 'recebido' soma no estoque (uma única vez).

    Recebido e cancelado são finais: o pedido não muda mais."""
    pedido = Pedido.objects.select_for_update().select_related('consumivel').get(pk=pedido_id)
    if pedido.status in Pedido.FINAIS or novo_status == pedido.status:
        return pedido

    pedido.status = novo_status
    campos = ['status']
    if novo_status in Pedido.FINAIS:
        pedido.finalizado_em = timezone.now()
        pedido.finalizado_por = _nome_do_usuario(usuario) if usuario else ''
        campos += ['finalizado_em', 'finalizado_por']
    pedido.save(update_fields=campos)

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


class ValorMudou(Exception):
    """Outra pessoa mudou o número enquanto o formulário estava aberto."""


class SemEstoque(Exception):
    """O estoque da unidade não tem a quantidade necessária."""

    def __init__(self, item):
        super().__init__(item.nome)
        self.item = item


def _nome_do_usuario(usuario):
    if not usuario.is_authenticated:
        return ''
    return usuario.get_full_name() or usuario.get_username()


def _valor_final(atual, enviado, original):
    """Decide o valor a gravar a partir do que estava na tela (original) e do que foi enviado.

    Campo que a pessoa não mexeu mantém o valor atual do banco (que outra pessoa pode ter
    mudado nesse meio-tempo). Se os dois mudaram, recusa para não apagar a mudança do outro."""
    if original is None or enviado == atual:
        return enviado
    if enviado == original:
        return atual
    if atual != original:
        raise ValorMudou
    return enviado


@transaction.atomic
def atualizar_contagem(impressora_id, niveis, residuo, usuario):
    """Grava níveis, reservas na sala e caixa de resíduo vindos do card da impressora.

    `niveis` é {cor: ((nivel, original), (na_sala, original))} e `residuo` é (valor, original),
    em que original é o número que estava na tela (ou None). Mudança na reserva fica registrada
    como ajuste de contagem. Levanta ValorMudou se outra pessoa mudou o mesmo número antes."""
    impressora = Impressora.objects.select_for_update().get(pk=impressora_id)
    ajustes = []
    linhas = list(NivelToner.objects.select_for_update().filter(impressora=impressora))
    for linha in linhas:
        if linha.cor not in niveis:  # cor nova (o modelo mudou depois que a tela abriu)
            continue
        (nivel, nivel_orig), (sala, sala_orig) = niveis[linha.cor]
        sala = _valor_final(linha.na_sala, sala, sala_orig)
        if sala != linha.na_sala:
            ajustes.append(('Toner ' + linha.get_cor_display(), linha.cor, linha.na_sala, sala))
        linha.nivel = _valor_final(linha.nivel, nivel, nivel_orig)
        linha.na_sala = sala
    residuo = _valor_final(impressora.residuo_na_sala, *residuo)
    if residuo != impressora.residuo_na_sala:
        ajustes.append(('Caixa de resíduo', '', impressora.residuo_na_sala, residuo))

    for linha in linhas:  # salva mesmo sem mudança: marca os níveis como conferidos agora
        linha.save(update_fields=['nivel', 'na_sala'])
    impressora.residuo_na_sala = residuo
    impressora.save(update_fields=['residuo_na_sala'])
    for descricao, cor, anterior, novo in ajustes:  # contagem corrigida à mão fica registrada
        AjusteReserva.objects.create(
            impressora=impressora, impressora_nome=impressora.nome, descricao=descricao, cor=cor,
            anterior=anterior, novo=novo, usuario=usuario if usuario.is_authenticated else None,
            usuario_nome=_nome_do_usuario(usuario))
    return impressora


@transaction.atomic
def ajustar_estoque(consumivel_id, novo, usuario, original=None):
    """Corrige à mão a quantidade no estoque da unidade e registra o ajuste.

    `original` é o número que estava na tela; se o estoque mudou desde então, levanta ValorMudou."""
    item = Consumivel.objects.select_for_update().get(pk=consumivel_id)
    anterior = item.estoque_unidade
    item.estoque_unidade = _valor_final(anterior, novo, original)
    item.save(update_fields=['estoque_unidade'])  # mesmo sem mudança: marca como conferido agora
    if item.estoque_unidade == anterior:
        return None
    return AjusteEstoque.objects.create(
        item=item, item_nome=item.nome, anterior=anterior, novo=item.estoque_unidade,
        usuario=usuario if usuario.is_authenticated else None, usuario_nome=_nome_do_usuario(usuario))


def _devolver_ao_estoque(impressora, item_id, quantidade, descricao, cor, usuario, motivo):
    """Tira `quantidade` da reserva da sala e soma no estoque do item, registrando os dois lados."""
    nome = _nome_do_usuario(usuario)
    usuario = usuario if usuario.is_authenticated else None
    AjusteReserva.objects.create(
        impressora=impressora, impressora_nome=impressora.nome, cor=cor,
        descricao=f'{descricao} (devolvido ao estoque)', anterior=quantidade, novo=0,
        usuario=usuario, usuario_nome=nome)
    if item_id is None:  # não estava ligado a um item do estoque: só sai da contagem da sala
        return None
    item = Consumivel.objects.select_for_update().get(pk=item_id)
    anterior = item.estoque_unidade
    item.estoque_unidade += quantidade
    item.save(update_fields=['estoque_unidade'])
    AjusteEstoque.objects.create(item=item, item_nome=item.nome, anterior=anterior,
                                 novo=item.estoque_unidade, motivo=motivo,
                                 usuario=usuario, usuario_nome=nome)
    return f'{quantidade}x {item.nome}'


@transaction.atomic
def mudar_modelo(impressora_id, novo_modelo, usuario):
    """Troca o modelo da impressora e devolve ao estoque a reserva da sala que não serve mais.

    Em cada cor (e na caixa de resíduo), se o modelo novo usa o mesmo item, a reserva e o nível
    continuam. Se usa outro item, a reserva volta para o estoque do item antigo e a cor recomeça
    com nível 100% e reserva 0. Retorna a lista do que foi devolvido (ex.: "1x Konica Toner Ciano")."""
    impressora = (Impressora.objects.select_for_update()
                  .select_related('modelo').get(pk=impressora_id))
    antigo = impressora.modelo
    if antigo.pk == novo_modelo.pk:
        return []
    item_antigo = {t.cor: t.consumivel_id for t in antigo.toners.all()}
    item_novo = {t.cor: t.consumivel_id for t in novo_modelo.toners.all()}
    motivo = f'Devolvido da {impressora.nome}: modelo trocado de {antigo.nome} para {novo_modelo.nome}'

    devolvidos = []
    for linha in NivelToner.objects.select_for_update().filter(impressora=impressora):
        item_id = item_antigo.get(linha.cor)
        if item_id is not None and item_id == item_novo.get(linha.cor):
            continue  # mesmo toner nos dois modelos: a reserva continua servindo
        if linha.na_sala:
            devolvidos.append(_devolver_ao_estoque(impressora, item_id, linha.na_sala,
                                                   'Toner ' + linha.get_cor_display(), linha.cor,
                                                   usuario, motivo))
        linha.delete()  # sincronizar_niveis recria a cor, se o modelo novo usar, com 100% e reserva 0

    if impressora.residuo_na_sala and antigo.caixa_residuo_id != novo_modelo.caixa_residuo_id:
        devolvidos.append(_devolver_ao_estoque(impressora, antigo.caixa_residuo_id,
                                               impressora.residuo_na_sala, 'Caixa de resíduo', '',
                                               usuario, motivo))
        impressora.residuo_na_sala = 0

    impressora.modelo = novo_modelo
    impressora.save(update_fields=['modelo', 'residuo_na_sala'])  # refaz os níveis por cor
    return [d for d in devolvidos if d]


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
