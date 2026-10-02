from .acesso import eh_admin


def perfil(request):
    return {'pode_editar': eh_admin(request.user)}
