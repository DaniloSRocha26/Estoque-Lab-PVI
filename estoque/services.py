from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (ORDEM_CORES, Consumivel, Impressora, ModeloImpressora, ModeloToner,
                     NivelToner, Pedido, Troca)
from .niveis import DIAS_DESATUALIZADO

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


@transaction.atomic
def trocar_toner(impressora_id, cor, usuario):
    """Troca de toner em um clique: tira 1 da reserva da sala, volta o nível a 100% e registra."""
    nivel = (NivelToner.objects.select_for_update()
             .select_related('impressora__modelo').get(impressora_id=impressora_id, cor=cor))
    if nivel.na_sala < 1:
        raise SemReserva
    impressora = nivel.impressora
    ligacao = (ModeloToner.objects.select_related('consumivel')
               .filter(modelo=impressora.modelo, cor=cor).first())
    toner = ligacao.consumivel if ligacao else None
    nome_usuario = (usuario.get_full_name() or usuario.get_username()) if usuario.is_authenticated else ''

    troca = Troca.objects.create(
        impressora=impressora, impressora_nome=impressora.nome, cor=cor,
        toner=toner, toner_nome=toner.nome if toner else '',
        nivel_anterior=nivel.nivel,
        usuario=usuario if usuario.is_authenticated else None, usuario_nome=nome_usuario)
    nivel.na_sala -= 1
    nivel.nivel = 100
    nivel.save(update_fields=['na_sala', 'nivel'])
    return troca
