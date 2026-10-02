from collections import defaultdict

from django.db import transaction

from .models import Consumivel, Impressora, Pedido

STATUS_EM_ANDAMENTO = ('pendente', 'enviado')


def impressoras_com_niveis():
    """Impressoras com níveis por cor e o nome do toner de cada cor já anexados."""
    impressoras = list(
        Impressora.objects.select_related('modelo', 'modelo__caixa_residuo')
        .prefetch_related('modelo__toners__consumivel', 'niveis')
        .order_by('localizacao', 'nome')
    )
    for imp in impressoras:
        toner_da_cor = {t.cor: t.consumivel for t in imp.modelo.toners.all()}
        imp.colorida = len(toner_da_cor) > 1
        imp.linhas = imp.niveis_ordenados()
        for linha in imp.linhas:
            linha.toner = toner_da_cor.get(linha.cor)
        imp.sem_reserva_sala = any(l.na_sala == 0 for l in imp.linhas)
        imp.nivel_minimo = min((l.nivel for l in imp.linhas), default=100)
    return impressoras


def calcular_alertas():
    """Itens com estoque abaixo do mínimo e ao menos uma impressora sem reserva na sala."""
    sem_reserva = defaultdict(list)  # consumivel_id -> nomes das impressoras (e cor) sem reserva
    for imp in impressoras_com_niveis():
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
