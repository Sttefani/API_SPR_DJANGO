# ocorrencias/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated
from usuarios.permissions import IsSuperAdminUser


class OcorrenciaPermission(BasePermission):
    """
    Permissão principal para a OcorrenciaViewSet.
    """
    def has_permission(self, request, view):
        # Barreira 1: Precisa estar logado para qualquer ação.
        if not IsAuthenticated().has_permission(request, view):
            return False

        # Barreira 2: Apenas Super Admin pode deletar.
        if request.method == 'DELETE':
            return IsSuperAdminUser().has_permission(request, view)
        
        # Barreira 3: O perfil ADMINISTRATIVO não pode criar.
        if request.method == 'POST':
            return request.user.perfil != 'ADMINISTRATIVO'

        # Permite outras ações como GET, PUT, PATCH para a lógica do serializer decidir.
        return True


class PodeFinalizarOcorrencia(BasePermission):
    """
    Permite a ação de finalizar apenas para perfis Administrativo ou Super Admin.
    """
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (user.perfil in ['ADMINISTRATIVO', 'SUPER_ADMIN'])


class PodeReabrirOcorrencia(BasePermission):
    """
    Permite a ação de reabrir apenas para Super Admin.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser


class PodeEditarOcorrencia(BasePermission):
    """
    Permissão específica para edição baseada no objeto.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        if user.perfil == 'ADMINISTRATIVO':
            return True # A lógica do que ele pode editar está no serializer
        if obj.perito_atribuido:
            return user.id == obj.perito_atribuido.id
        return user.perfil in ['PERITO', 'OPERACIONAL']
    
    
class PeritoAtribuidoRequired(BasePermission):
    """
    Permissão que verifica se a ocorrência (o 'obj') já tem um perito atribuído.
    """
    message = "É necessário atribuir um perito à ocorrência antes de gerenciar os exames."

    def has_object_permission(self, request, view, obj):
        # 'obj' aqui é a instância da ocorrência que estamos tentando acessar.
        # A permissão é concedida se o campo 'perito_atribuido' não for nulo.
        return obj.perito_atribuido is not None
    
class PodeVerRelatoriosGerenciais(BasePermission):
    """
    Permite o acesso a relatórios e estatísticas gerenciais apenas para perfis
    ADMINISTRATIVO ou Super Admin.
    """
    message = "Você não tem permissão para acessar informações gerenciais."

    def has_permission(self, request, view):
        # Garante que o usuário está logado antes de qualquer verificação
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Libera o acesso se for Super Admin OU se tiver o perfil ADMINISTRATIVO
        return request.user.is_superuser or request.user.perfil == 'ADMINISTRATIVO'

# --- FIM DO NOVO CÓDIGO ---