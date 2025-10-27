# usuarios/permissions.py

from rest_framework.permissions import BasePermission


class IsSuperAdminUser(BasePermission):
    """
    Permite acesso apenas a usuários que são superusuários.
    """

    def has_permission(self, request, view):
        # A permissão é concedida se o usuário estiver autenticado
        # e for um superusuário.
        return bool(request.user and request.user.is_superuser)
