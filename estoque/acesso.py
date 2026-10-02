from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps

GRUPO_ADMIN = 'admin'
GRUPO_VISUALIZADOR = 'visualizador'


def eh_admin(user):
    """Admin = superusuário ou membro do grupo 'admin'. Quem não é admin só consulta."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=GRUPO_ADMIN).exists()


def somente_admin(view):
    """Exige login e perfil admin; visualizador recebe 403."""
    @wraps(view)
    def interna(request, *args, **kwargs):
        if not eh_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return login_required(interna)
