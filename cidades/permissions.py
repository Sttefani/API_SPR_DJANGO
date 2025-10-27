# cidades/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated


class CidadePermission(BasePermission):
    """
    Permissão customizada para o modelo Cidade.
    - Apenas Super Admin pode deletar (ação 'destroy').
    - Qualquer usuário autenticado pode fazer o resto.
    """

    def has_permission(self, request, view):
        # Primeira barreira: precisa estar logado.
        if not IsAuthenticated().has_permission(request, view):
            return False

        # AÇÃO DE DELEÇÃO: A ação que o router cria para o botão 'Delete' é a 'destroy'.
        if view.action == "destroy":
            # Retorna True apenas se o usuário for superuser.
            return request.user.is_superuser

        # Para todas as outras ações ('list', 'create', 'retrieve', 'update'),
        # permite o acesso para qualquer usuário autenticado.
        return True
