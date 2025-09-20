from rest_framework.permissions import BasePermission, IsAuthenticated # <-- ESTA LINHA CORRIGE O ERRO
from usuarios.permissions import IsSuperAdminUser

class CidadePermission(BasePermission):
    """
    Permissão customizada para o modelo Cidade:
    - Apenas Super Admin pode deletar (DELETE).
    - Qualquer usuário autenticado pode fazer o resto (GET, POST, PUT, PATCH).
    """
    def has_permission(self, request, view):
        if request.method == 'DELETE':
            return IsSuperAdminUser().has_permission(request, view)

        return IsAuthenticated().has_permission(request, view)