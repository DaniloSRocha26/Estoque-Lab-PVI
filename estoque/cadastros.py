from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .acesso import somente_admin
from .forms import (ConsumivelEditarForm, ConsumivelNovoForm, ImpressoraForm, ModeloNomeForm,
                    ModeloNovoForm)
from .models import Consumivel, Impressora, ModeloImpressora
from .services import ValorMudou, ajustar_estoque, criar_modelo, mudar_modelo
from .usuarios import listar_usuarios


def _erros(request, form):
    for campo, lista in form.errors.items():
        rotulo = form.fields[campo].label or campo if campo in form.fields else ''
        for erro in lista:
            messages.error(request, f'{rotulo.capitalize()}: {erro}' if rotulo else erro)


def _salvar(request, form, sucesso):
    if form.is_valid():
        form.save()
        messages.success(request, sucesso)
    else:
        _erros(request, form)


def _excluir(request, objeto, sucesso, em_uso):
    try:
        objeto.delete()
        messages.success(request, sucesso)
    except ProtectedError:
        messages.error(request, em_uso)


@somente_admin
def cadastros(request):
    return render(request, 'estoque/cadastros.html', {
        'impressoras': Impressora.objects.select_related('modelo').order_by('modelo__nome', 'nome'),
        'modelos': ModeloImpressora.objects.select_related('caixa_residuo')
                   .prefetch_related('toners__consumivel', 'impressora_set').order_by('nome'),
        'consumiveis': Consumivel.objects.order_by('tipo', 'nome'),
        'usuarios': listar_usuarios(request.user),
    })


# ---- Impressoras ----
@somente_admin
@require_POST
def impressora_criar(request):
    _salvar(request, ImpressoraForm(request.POST), 'Impressora cadastrada.')
    return redirect('cadastros')


@somente_admin
@require_POST
def impressora_editar(request, pk):
    obj = get_object_or_404(Impressora, pk=pk)
    form = ImpressoraForm(request.POST, instance=obj)
    if not form.is_valid():
        _erros(request, form)
        return redirect('cadastros')
    with transaction.atomic():
        # o modelo passa por mudar_modelo, que devolve ao estoque a reserva que não serve mais
        form.save(commit=False).save(update_fields=['nome', 'numero_serie', 'localizacao'])
        devolvidos = mudar_modelo(obj.id, form.cleaned_data['modelo'], request.user)
    mensagem = f'{obj.nome} atualizada.'
    if devolvidos:
        mensagem += ' Voltaram ao estoque: ' + ', '.join(devolvidos) + '.'
    messages.success(request, mensagem)
    return redirect('cadastros')


@somente_admin
@require_POST
def impressora_excluir(request, pk):
    obj = get_object_or_404(Impressora, pk=pk)
    _excluir(request, obj, f'{obj.nome} excluída.', 'Não foi possível excluir a impressora.')
    return redirect('cadastros')


# ---- Modelos ----
@somente_admin
@require_POST
def modelo_criar(request):
    form = ModeloNovoForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        criar_modelo(d['nome'], d['tipo'] == 'colorida', d['usa_residuo'], d['estoque_minimo'])
        messages.success(request, f'Modelo {d["nome"]} criado com os toners.')
    else:
        _erros(request, form)
    return redirect('cadastros')


@somente_admin
@require_POST
def modelo_renomear(request, pk):
    obj = get_object_or_404(ModeloImpressora, pk=pk)
    _salvar(request, ModeloNomeForm(request.POST, instance=obj), 'Modelo renomeado.')
    return redirect('cadastros')


@somente_admin
@require_POST
def modelo_excluir(request, pk):
    obj = get_object_or_404(ModeloImpressora, pk=pk)
    _excluir(request, obj, f'Modelo {obj.nome} excluído.',
             'Este modelo ainda tem impressoras cadastradas. Exclua ou mude as impressoras antes.')
    return redirect('cadastros')


# ---- Itens de estoque ----
@somente_admin
@require_POST
def consumivel_criar(request):
    _salvar(request, ConsumivelNovoForm(request.POST), 'Item criado.')
    return redirect('cadastros')


@somente_admin
@require_POST
def consumivel_editar(request, pk):
    obj = get_object_or_404(Consumivel, pk=pk)
    form = ConsumivelEditarForm(request.POST, instance=obj)
    if not form.is_valid():
        _erros(request, form)
        return redirect('cadastros')
    original = request.POST.get('orig_estoque_unidade', '')
    try:
        with transaction.atomic():
            form.save(commit=False).save(update_fields=['nome', 'estoque_minimo'])
            ajustar_estoque(obj.id, form.cleaned_data['estoque_unidade'], request.user,
                            int(original) if original.isdigit() else None)
    except ValorMudou:
        messages.error(request, f'Outra pessoa mudou o estoque de {obj.nome} enquanto você editava. '
                                'Confira o número novo e salve de novo.')
    else:
        messages.success(request, f'{obj.nome} atualizado.')
    return redirect('cadastros')


@somente_admin
@require_POST
def consumivel_excluir(request, pk):
    obj = get_object_or_404(Consumivel, pk=pk)
    _excluir(request, obj, f'{obj.nome} excluído.',
             'Este item está em uso (modelo ou pedido) e não pode ser excluído.')
    return redirect('cadastros')
