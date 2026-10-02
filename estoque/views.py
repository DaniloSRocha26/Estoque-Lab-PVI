from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .acesso import somente_admin
from .models import (CORES, ORDEM_CORES, Consumivel, Impressora, ModeloToner, NivelToner, Pedido,
                     AjusteReserva, Reposicao, Troca)
from .niveis import NIVEL_BAIXO
from .services import (STATUS_EM_ANDAMENTO, SemEstoque, SemReserva, calcular_alertas,
                       impressoras_com_niveis, mudar_status_pedido, repor_na_sala, repor_tudo,
                       salas_para_reabastecer, trocar_toner)



def _inteiro(valor, minimo=0, maximo=None):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    if numero < minimo or (maximo is not None and numero > maximo):
        return None
    return numero


def _contexto_base():
    """Dados do aviso geral, usados no topo das páginas Estoque e Impressoras."""
    impressoras = impressoras_com_niveis()
    consumiveis = list(Consumivel.objects.order_by('tipo', 'nome'))
    cor_do_item = dict(ModeloToner.objects.order_by('-id').values_list('consumivel_id', 'cor'))
    for c in consumiveis:
        c.cor = cor_do_item.get(c.id)  # só toners ligados a um modelo têm cor
        c.cor_nome = dict(CORES).get(c.cor)
    alertas = calcular_alertas(impressoras)
    reabastecer = salas_para_reabastecer(impressoras)
    return {
        'impressoras': impressoras,
        'consumiveis': consumiveis,
        'alertas': alertas,
        'reabastecer': reabastecer,
        'resumo': {
            'impressoras': len(impressoras),
            'nivel_baixo': sum(1 for i in impressoras if i.nivel_minimo <= NIVEL_BAIXO),
            'abaixo_minimo': sum(1 for c in consumiveis if c.estoque_unidade < c.estoque_minimo),
            'pedidos_abertos': Pedido.objects.filter(status__in=STATUS_EM_ANDAMENTO).count(),
            'reabastecer': len(reabastecer),
        },
    }


def pagina_estoque(request):
    return render(request, 'estoque/estoque.html', _contexto_base())


def pagina_impressoras(request):
    contexto = _contexto_base()
    por_modelo = {}
    for imp in contexto['impressoras']:
        por_modelo.setdefault(imp.modelo, []).append(imp)
    contexto['grupos'] = [
        {'modelo': m, 'impressoras': lista}
        for m, lista in sorted(por_modelo.items(), key=lambda par: par[0].nome.lower())]
    return render(request, 'estoque/impressoras.html', contexto)


@somente_admin
@require_POST
def atualizar_impressora(request, pk):
    impressora = get_object_or_404(Impressora, pk=pk)
    residuo = _inteiro(request.POST.get('residuo_na_sala'))
    novos, ajustes = [], []
    for linha in impressora.niveis.all():
        nivel = _inteiro(request.POST.get(f'nivel_{linha.cor}'), 0, 100)
        na_sala = _inteiro(request.POST.get(f'sala_{linha.cor}'))
        if nivel is None or na_sala is None:
            residuo = None
            break
        if na_sala != linha.na_sala:
            ajustes.append(('Toner ' + linha.get_cor_display(), linha.cor, linha.na_sala, na_sala))
        linha.nivel, linha.na_sala = nivel, na_sala
        novos.append(linha)

    if residuo is None:
        messages.error(request, 'Valores inválidos. O nível deve ficar entre 0 e 100.')
    else:
        if residuo != impressora.residuo_na_sala:
            ajustes.append(('Caixa de resíduo', '', impressora.residuo_na_sala, residuo))
        with transaction.atomic():
            for linha in novos:
                linha.save(update_fields=['nivel', 'na_sala'])
            impressora.residuo_na_sala = residuo
            impressora.save(update_fields=['residuo_na_sala'])
            for descricao, cor, anterior, novo in ajustes:  # contagem corrigida à mão fica registrada
                AjusteReserva.objects.create(
                    impressora=impressora, impressora_nome=impressora.nome, descricao=descricao,
                    cor=cor, anterior=anterior, novo=novo, usuario=request.user,
                    usuario_nome=request.user.get_full_name() or request.user.get_username())
        messages.success(request, f'{impressora.nome} atualizada.')
    return redirect('impressoras')


@somente_admin
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
    return redirect('estoque')


def pedidos(request):
    return render(request, 'estoque/pedidos.html', {
        'pedidos': Pedido.objects.select_related('consumivel').order_by('-criado_em'),
        'consumiveis': Consumivel.objects.order_by('tipo', 'nome'),
        'status_opcoes': Pedido.STATUS,
    })


@somente_admin
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
    return redirect(voltar if voltar in ('estoque', 'impressoras', 'pedidos') else 'pedidos')


@somente_admin
@require_POST
def status_pedido(request, pk):
    novo = request.POST.get('status')
    if novo not in dict(Pedido.STATUS):
        messages.error(request, 'Status inválido.')
    else:
        pedido = mudar_status_pedido(pk, novo)
        messages.success(request, f'Pedido atualizado para "{pedido.get_status_display()}".')
    return redirect('pedidos')


@somente_admin
@require_POST
def trocar_toner_view(request, pk, cor):
    impressora = get_object_or_404(Impressora, pk=pk)
    if cor not in ORDEM_CORES:
        raise Http404
    get_object_or_404(NivelToner, impressora=impressora, cor=cor)
    nome_cor = dict(CORES)[cor]
    origem = 'estoque' if request.POST.get('origem') == 'estoque' else 'sala'
    try:
        trocar_toner(impressora.id, cor, request.user, origem)
    except SemReserva:
        messages.error(request, f'Não há toner {nome_cor.lower()} de reserva na sala da {impressora.nome}. '
                                'Se pegou do estoque, use "Peguei do estoque".')
    except SemEstoque as erro:
        messages.error(request, f'Não há {erro.item.nome} no estoque da unidade.')
    else:
        de_onde = 'da reserva da sala' if origem == 'sala' else 'do estoque da unidade'
        messages.success(request, f'Troca registrada: {impressora.nome}, {nome_cor} (toner {de_onde}). '
                                  'O nível voltou para 100%.')
    return redirect('impressoras')


@somente_admin
@require_POST
def repor_na_sala_view(request, pk, chave):
    impressora = get_object_or_404(Impressora, pk=pk)
    if chave != 'residuo' and chave not in ORDEM_CORES:
        raise Http404
    try:
        reposicao = repor_na_sala(impressora.id, chave, request.user)
    except NivelToner.DoesNotExist:
        raise Http404
    except SemEstoque as erro:
        messages.error(request, f'Sem estoque de {erro.item.nome}. Faça um pedido para poder repor.')
    except ValueError as erro:
        messages.error(request, str(erro))
    else:
        if reposicao is None:
            messages.success(request, f'{impressora.nome} já tem a reserva ideal.')
        else:
            messages.success(request, f'Reposto: {reposicao.quantidade}x {reposicao.item_nome} na {impressora.nome}.')
    return redirect('estoque')


@somente_admin
@require_POST
def repor_tudo_view(request):
    feitas, sem_estoque = repor_tudo(request.user)
    if feitas:
        messages.success(request, f'{len(feitas)} reposição(ões) feita(s) na sala.')
    if sem_estoque:
        itens = sorted({linha['item'].nome for linha in sem_estoque})
        messages.error(request, 'Sem estoque para repor: ' + ', '.join(itens) + '.')
    if not feitas and not sem_estoque:
        messages.success(request, 'Todas as salas já têm a reserva ideal.')
    return redirect('estoque')


def pagina_historico(request):
    trocas = Troca.objects.select_related('impressora')
    reposicoes = Reposicao.objects.select_related('impressora')
    ajustes = AjusteReserva.objects.select_related('impressora')
    escolhida = request.GET.get('impressora', '')
    if escolhida.isdigit():
        trocas = trocas.filter(impressora_id=int(escolhida))
        reposicoes = reposicoes.filter(impressora_id=int(escolhida))
        ajustes = ajustes.filter(impressora_id=int(escolhida))
    else:
        escolhida = ''
    return render(request, 'estoque/historico.html', {
        'trocas': trocas[:300],
        'reposicoes': reposicoes[:300],
        'ajustes': ajustes[:300],
        'impressoras': Impressora.objects.order_by('nome'),
        'escolhida': escolhida,
    })
