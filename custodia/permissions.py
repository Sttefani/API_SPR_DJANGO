# custodia/permissions.py

from rest_framework.permissions import BasePermission
from usuarios.models import User


def _is_externo(user):
    return user.perfil == User.Perfil.EXTERNO


class PodeCustodiar(BasePermission):
    """Escrita no módulo: todos os perfis internos exceto EXTERNO."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return not _is_externo(request.user)


class PodeVerCustodia(BasePermission):
    """Leitura: qualquer usuário autenticado e ativo."""
    def has_permission(self, request, view):
        return request.user.is_authenticated
