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


class CidadePermission(BasePermission):
    """
    Permissão customizada para o modelo Cidade:
    - Apenas Super Admin pode deletar (DELETE).
    - Qualquer usuário autenticado pode fazer o resto (GET, POST, PUT, PATCH).
    """

    def has_permission(self, request, view):
        # Se o método for DELETE, aplicamos a permissão de Super Admin.
        if request.method == 'DELETE':
            return IsSuperAdminUser().has_permission(request, view)

        # Para todos os outros métodos, basta estar autenticado.
        return IsAuthenticated().has_permission(request, view)