from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .acesso import somente_admin
from .models import (CORES, ORDEM_CORES, AjusteEstoque, AjusteReserva, Consumivel, Impressora,
                     ModeloImpressora, ModeloToner, NivelToner, Pedido, Reposicao, Troca)
from .niveis import NIVEL_BAIXO
from .services import (STATUS_EM_ANDAMENTO, SemEstoque, SemReserva, ValorMudou, ajustar_estoque,
                       atualizar_contagem, calcular_alertas, impressoras_com_niveis,
                       mudar_status_pedido, repor_na_sala, repor_tudo, salas_para_reabastecer,
                       trocar_toner)

LIMITE_HISTORICO = 300
MENSAGEM_VALOR_MUDOU = ('Outra pessoa mudou {} enquanto você editava. A tela foi atualizada com os '
                        'números novos: confira e salve de novo.')


def _inteiro(valor, minimo=0, maximo=None):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    if numero < minimo or (maximo is not None and numero > maximo):
        return None
    return numero


def _enviado_e_original(post, campo, maximo=None):
    """(valor enviado, valor que estava na tela). O original vem no campo oculto "orig_<campo>"."""
    return _inteiro(post.get(campo), 0, maximo), _inteiro(post.get(f'orig_{campo}'), 0, maximo)


def _contexto_base():
    """Dados do aviso geral, usados no topo das páginas Estoque e Impressoras."""
    impressoras = impressoras_com_niveis()
    consumiveis = list(Consumivel.objects.order_by('tipo', 'nome'))
    cor_do_item = dict(ModeloToner.objects.order_by('-id').values_list('consumivel_id', 'cor'))
    for c in consumiveis:
        c.cor = cor_do_item.get(c.id)  # só toners ligados a um modelo têm cor
        c.cor_nome = dict(CORES).get(c.cor)
    alertas = calcular_alertas(impressoras)
    por_id = {c.id: c for c in consumiveis}
    for a in alertas:  # usa o item já com a cor do toner, para a bolinha na tabela
        a['consumivel'] = por_id.get(a['consumivel'].id, a['consumivel'])
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


def _estoque_por_modelo(consumiveis):
    """Itens do estoque agrupados pelo modelo que os usa: toners na ordem das cores, depois a caixa."""
    por_id = {c.id: c for c in consumiveis}
    usados, grupos = set(), []
    modelos = (ModeloImpressora.objects.select_related('caixa_residuo')
               .prefetch_related('toners').order_by('nome'))
    for modelo in modelos:
        ids = [t.consumivel_id for t in modelo.toners_ordenados()] + [modelo.caixa_residuo_id]
        itens = [por_id[i] for i in ids if i in por_id and i not in usados]
        usados.update(ids)
        if itens:
            grupos.append({'nome': modelo.nome, 'itens': itens})
    outros = [c for c in consumiveis if c.id not in usados]
    if outros:
        grupos.append({'nome': 'Outros itens', 'itens': outros})
    return grupos


def pagina_estoque(request):
    contexto = _contexto_base()
    contexto['grupos_estoque'] = _estoque_por_modelo(contexto['consumiveis'])
    return render(request, 'estoque/estoque.html', contexto)


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
    niveis = {cor: (_enviado_e_original(request.POST, f'nivel_{cor}', 100),
                    _enviado_e_original(request.POST, f'sala_{cor}'))
              for cor in impressora.niveis.values_list('cor', flat=True)}
    residuo = _enviado_e_original(request.POST, 'residuo_na_sala')

    if residuo[0] is None or any(n[0] is None or s[0] is None for n, s in niveis.values()):
        messages.error(request, 'Valores inválidos. O nível deve ficar entre 0 e 100.')
        return redirect('impressoras')
    try:
        atualizar_contagem(impressora.id, niveis, residuo, request.user)
    except ValorMudou:
        messages.error(request, MENSAGEM_VALOR_MUDOU.format(f'a {impressora.nome}'))
    else:
        messages.success(request, f'{impressora.nome} atualizada.')
    return redirect('impressoras')


@somente_admin
@require_POST
def atualizar_consumivel(request, pk):
    consumivel = get_object_or_404(Consumivel, pk=pk)
    estoque, original = _enviado_e_original(request.POST, 'estoque_unidade')
    if estoque is None:
        messages.error(request, 'Quantidade inválida.')
        return redirect('estoque')
    try:
        ajustar_estoque(consumivel.id, estoque, request.user, original)
    except ValorMudou:
        messages.error(request, MENSAGEM_VALOR_MUDOU.format(f'o estoque de {consumivel.nome}'))
    else:
        messages.success(request, f'Estoque de {consumivel.nome} atualizado.')
    return redirect('estoque')


def pedidos(request):
    todos = Pedido.objects.select_related('consumivel')
    finalizados = todos.filter(status__in=Pedido.FINAIS).order_by('-finalizado_em', '-criado_em')
    return render(request, 'estoque/pedidos.html', {
        'a_caminho': todos.filter(status__in=STATUS_EM_ANDAMENTO).order_by('criado_em'),
        'finalizados': finalizados[:LIMITE_HISTORICO],
        'finalizados_total': finalizados.count(),
        'consumiveis': Consumivel.objects.order_by('tipo', 'nome'),
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
        pedido = mudar_status_pedido(get_object_or_404(Pedido, pk=pk).pk, novo, request.user)
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
    listas = {
        'trocas': Troca.objects.all(),
        'reposicoes': Reposicao.objects.all(),
        'ajustes': AjusteReserva.objects.all(),
        'ajustes_estoque': AjusteEstoque.objects.all(),
    }
    escolhida = request.GET.get('impressora', '')
    if escolhida.isdigit():
        for chave in ('trocas', 'reposicoes', 'ajustes'):
            listas[chave] = listas[chave].filter(impressora_id=int(escolhida))
        listas['ajustes_estoque'] = listas['ajustes_estoque'].none()  # não são de uma impressora
    else:
        escolhida = ''
    contexto = {chave: qs[:LIMITE_HISTORICO] for chave, qs in listas.items()}
    contexto.update({
        'totais': {chave: qs.count() for chave, qs in listas.items()},
        'limite': LIMITE_HISTORICO,
        'impressoras': Impressora.objects.order_by('nome'),
        'escolhida': escolhida,
    })
    return render(request, 'estoque/historico.html', contexto)
