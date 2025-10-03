from rest_framework.permissions import BasePermission, SAFE_METHODS


class ServicoPericialPermission(BasePermission):
    """
    GET/OPTIONS/HEAD: Qualquer usuário autenticado
    POST/PUT/PATCH/DELETE: Apenas Super Admin
    """
    def has_permission(self, request, view):
        # Leitura: todos os usuários autenticados
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Escrita: apenas super admin
        return request.user and request.user.is_superuser