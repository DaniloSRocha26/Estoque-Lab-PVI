from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Consumivel, Impressora, Pedido
from .services import (STATUS_EM_ANDAMENTO, calcular_alertas, impressoras_com_niveis,
                       mudar_status_pedido)

NIVEL_BAIXO = 15  # % considerado baixo (provisório, ver pendências do projeto)


def _inteiro(valor, minimo=0, maximo=None):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    if numero < minimo or (maximo is not None and numero > maximo):
        return None
    return numero


def painel(request):
    impressoras = impressoras_com_niveis()
    consumiveis = list(Consumivel.objects.order_by('tipo', 'nome'))
    return render(request, 'estoque/painel.html', {
        'impressoras': impressoras,
        'consumiveis': consumiveis,
        'alertas': calcular_alertas(),
        'resumo': {
            'impressoras': len(impressoras),
            'nivel_baixo': sum(1 for i in impressoras if i.nivel_minimo <= NIVEL_BAIXO),
            'abaixo_minimo': sum(1 for c in consumiveis if c.estoque_unidade < c.estoque_minimo),
            'pedidos_abertos': Pedido.objects.filter(status__in=STATUS_EM_ANDAMENTO).count(),
        },
    })


@require_POST
def atualizar_impressora(request, pk):
    impressora = get_object_or_404(Impressora, pk=pk)
    residuo = _inteiro(request.POST.get('residuo_na_sala'))
    novos = []
    for linha in impressora.niveis.all():
        nivel = _inteiro(request.POST.get(f'nivel_{linha.cor}'), 0, 100)
        na_sala = _inteiro(request.POST.get(f'sala_{linha.cor}'))
        if nivel is None or na_sala is None:
            residuo = None
            break
        linha.nivel, linha.na_sala = nivel, na_sala
        novos.append(linha)

    if residuo is None:
        messages.error(request, 'Valores inválidos. O nível deve ficar entre 0 e 100.')
    else:
        with transaction.atomic():
            for linha in novos:
                linha.save(update_fields=['nivel', 'na_sala'])
            impressora.residuo_na_sala = residuo
            impressora.save(update_fields=['residuo_na_sala'])
        messages.success(request, f'{impressora.nome} atualizada.')
    return redirect('painel')


@require_POST
def atualizar_consumivel(request, pk):
    consumivel = get_object_or_404(Consumivel, pk=pk)
    estoque = _inteiro(request.POST.get('estoque_unidade'))
    if estoque is None:
        messages.error(request, 'Quantidade inválida.')
    else:
        consumivel.estoque_unidade = estoque
        consumivel.save(update_fields=['estoque_unidade'])
        messages.success(request, f'Estoque de {consumivel.nome} atualizado.')
    return redirect('painel')


def pedidos(request):
    return render(request, 'estoque/pedidos.html', {
        'pedidos': Pedido.objects.select_related('consumivel').order_by('-criado_em'),
        'consumiveis': Consumivel.objects.order_by('tipo', 'nome'),
        'status_opcoes': Pedido.STATUS,
    })


@require_POST
def criar_pedido(request):
    consumivel = get_object_or_404(Consumivel, pk=request.POST.get('consumivel'))
    quantidade = _inteiro(request.POST.get('quantidade'), minimo=1)
    solicitante = request.POST.get('solicitante', '').strip()
    if quantidade is None or not solicitante:
        messages.error(request, 'Informe quantidade (mínimo 1) e o nome do solicitante.')
    else:
        Pedido.objects.create(
            consumivel=consumivel,
            quantidade=quantidade,
            solicitante=solicitante,
            observacao=request.POST.get('observacao', '').strip(),
        )
        messages.success(request, 'Pedido criado.')
    voltar = request.POST.get('voltar')
    return redirect(voltar if voltar in ('painel', 'pedidos') else 'pedidos')


@require_POST
def status_pedido(request, pk):
    novo = request.POST.get('status')
    if novo not in dict(Pedido.STATUS):
        messages.error(request, 'Status inválido.')
    else:
        pedido = mudar_status_pedido(pk, novo)
        messages.success(request, f'Pedido atualizado para "{pedido.get_status_display()}".')
    return redirect('pedidos')
