from django.db import transaction

from .models import Consumivel, Impressora, Pedido

STATUS_EM_ANDAMENTO = ('pendente', 'enviado')


def calcular_alertas():
    """Itens com estoque abaixo do mínimo e ao menos uma impressora sem reserva na sala."""
    impressoras = list(Impressora.objects.select_related('modelo'))
    em_andamento = set(
        Pedido.objects.filter(status__in=STATUS_EM_ANDAMENTO)
        .values_list('consumivel_id', flat=True)
    )

    alertas = []
    for item in Consumivel.objects.order_by('tipo', 'nome'):
        if item.estoque_unidade >= item.estoque_minimo:
            continue

        if item.tipo == 'toner':
            sem_reserva = [i for i in impressoras
                           if i.modelo.toner_id == item.id and i.toner_na_sala == 0]
        else:
            sem_reserva = [i for i in impressoras
                           if i.modelo.caixa_residuo_id == item.id and i.residuo_na_sala == 0]
        if not sem_reserva:
            continue

        alertas.append({
            'consumivel': item,
            'impressoras': sem_reserva,
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
