# protocolos/permissions.py

from rest_framework.permissions import BasePermission
from usuarios.models import User


class PodeEmitirProtocolo(BasePermission):
    """CUSTODIANTE, ADMINISTRATIVO e SUPER_ADMIN podem emitir protocolos."""
    message = 'Apenas Custodiante, Administrativo ou Super Admin podem emitir protocolos de saída.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return (
            request.user.perfil in {
                User.Perfil.CUSTODIANTE,
                User.Perfil.ADMINISTRATIVO,
                User.Perfil.SUPER_ADMIN,
            }
            or request.user.is_superuser
        )


class PodeVerProtocolo(BasePermission):
    """Qualquer usuário autenticado pode consultar protocolos."""
    def has_permission(self, request, view):
        return request.user.is_authenticated
