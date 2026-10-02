from .acesso import eh_admin
from .niveis import NIVEL_BAIXO, NIVEL_MEDIO


def perfil(request):
    return {
        'pode_editar': eh_admin(request.user),
        'NIVEL_BAIXO': NIVEL_BAIXO,
        'NIVEL_MEDIO': NIVEL_MEDIO,
    }
