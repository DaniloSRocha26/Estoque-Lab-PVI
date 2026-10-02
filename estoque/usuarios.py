from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .acesso import GRUPO_ADMIN, GRUPO_VISUALIZADOR, eh_admin, somente_admin

PERFIS = (GRUPO_ADMIN, GRUPO_VISUALIZADOR)


def listar_usuarios(usuario_atual):
    usuarios = list(User.objects.order_by('username'))
    for u in usuarios:
        u.perfil = GRUPO_ADMIN if eh_admin(u) else GRUPO_VISUALIZADOR
        u.e_voce = u.pk == usuario_atual.pk
    return usuarios


def _admins_ativos_exceto(usuario):
    return [u for u in User.objects.filter(is_active=True).exclude(pk=usuario.pk) if eh_admin(u)]


def _definir_perfil(usuario, perfil):
    usuario.groups.remove(*Group.objects.filter(name__in=PERFIS))
    usuario.groups.add(Group.objects.get(name=perfil))


def _senha_valida(request, senha, usuario=None):
    try:
        validate_password(senha, usuario)
    except ValidationError as erro:
        for msg in erro.messages:
            messages.error(request, f'Senha: {msg}')
        return False
    return True


@somente_admin
@require_POST
def usuario_criar(request):
    username = request.POST.get('username', '').strip()
    senha = request.POST.get('senha', '')
    perfil = request.POST.get('perfil')
    if not username or perfil not in PERFIS:
        messages.error(request, 'Informe o usuário e o perfil.')
    elif User.objects.filter(username__iexact=username).exists():
        messages.error(request, 'Já existe um usuário com esse nome.')
    elif _senha_valida(request, senha):
        usuario = User.objects.create_user(username, password=senha,
                                           first_name=request.POST.get('nome', '').strip())
        _definir_perfil(usuario, perfil)
        messages.success(request, f'Usuário {username} criado.')
    return redirect('cadastros')


@somente_admin
@require_POST
def usuario_editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    perfil = request.POST.get('perfil')
    ativo = request.POST.get('ativo') == 'on'
    nova_senha = request.POST.get('nova_senha', '')

    if perfil not in PERFIS:
        messages.error(request, 'Perfil inválido.')
        return redirect('cadastros')
    if usuario.is_superuser:  # superusuário é sempre admin e não pode ser rebaixado por aqui
        perfil, ativo = GRUPO_ADMIN, True
    perde_admin = eh_admin(usuario) and (perfil != GRUPO_ADMIN or not ativo)
    if perde_admin and not _admins_ativos_exceto(usuario):
        messages.error(request, 'Precisa existir pelo menos um administrador ativo.')
        return redirect('cadastros')
    if nova_senha and not _senha_valida(request, nova_senha, usuario):
        return redirect('cadastros')

    usuario.first_name = request.POST.get('nome', '').strip()
    usuario.is_active = ativo
    if nova_senha:
        usuario.set_password(nova_senha)
    usuario.save()
    if not usuario.is_superuser:
        _definir_perfil(usuario, perfil)
    messages.success(request, f'Usuário {usuario.username} atualizado.')
    return redirect('cadastros')


@somente_admin
@require_POST
def usuario_excluir(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, 'Você não pode excluir o seu próprio usuário.')
    elif eh_admin(usuario) and not _admins_ativos_exceto(usuario):
        messages.error(request, 'Precisa existir pelo menos um administrador ativo.')
    else:
        usuario.delete()
        messages.success(request, f'Usuário {usuario.username} excluído.')
    return redirect('cadastros')
