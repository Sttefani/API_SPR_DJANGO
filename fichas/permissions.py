# fichas/permissions.py - VERSÃO OTIMIZADA E SIMPLIFICADA

from rest_framework.permissions import BasePermission
from ocorrencias.models import Ocorrencia


class FichaPermission(BasePermission):
    """
    Permissão simplificada para fichas acessórias.
    
    REGRA ÚNICA: Herda TODAS as permissões da ocorrência pai.
    Se pode editar a ocorrência, pode editar a ficha.
    """

    def has_permission(self, request, view):
        """Verifica permissão básica (usuário logado e perfil válido)"""
        user = request.user
        
        if not user or not user.is_authenticated:
            return False

        # Super Admin pode tudo
        if user.is_superuser:
            return True
            
        # Perfis válidos
        return user.perfil in ['PERITO', 'OPERACIONAL', 'ADMINISTRATIVO']

    def has_object_permission(self, request, view, obj):
        """Verifica permissão no objeto específico (ficha ou sub-item)"""
        user = request.user
        
        if not user or not user.is_authenticated:
            return False

        # Encontra a ocorrência pai
        ocorrencia = self.get_ocorrencia_from_object(obj)
        if not ocorrencia:
            return False

        # Aplica as MESMAS regras da ocorrência
        return self.check_ocorrencia_permission(ocorrencia, user, request.method)

    def get_ocorrencia_from_object(self, obj):
        """Encontra a ocorrência pai de qualquer objeto"""
        # Ficha principal
        if hasattr(obj, 'ocorrencia'):
            return obj.ocorrencia
            
        # Sub-itens (vitima, vestigio)
        if hasattr(obj, 'ficha'):
            return obj.ficha.ocorrencia
            
        return None

    def check_ocorrencia_permission(self, ocorrencia, user, method):
        """
        Aplica as MESMAS regras de permissão da ocorrência.
        Centraliza toda a lógica aqui.
        """
        # Super Admin pode tudo
        if user.is_superuser:
            return True
        
        # Verifica se usuário tem acesso ao serviço pericial
        if user.perfil != 'ADMINISTRATIVO':
            if not user.servicos_periciais.filter(pk=ocorrencia.servico_pericial.pk).exists():
                return False
        
        # Administrativo: apenas leitura
        if user.perfil == 'ADMINISTRATIVO':
            return method in ['GET', 'HEAD', 'OPTIONS']
        
        # Leitura sempre permitida (para PERITO e OPERACIONAL do serviço)
        if method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # DELETE: apenas Super Admin (já verificado acima)
        if method == 'DELETE':
            return False
        
        # EDIÇÃO (PUT, POST, PATCH):
        
        # Se ocorrência finalizada: bloqueado
        if ocorrencia.esta_finalizada:
            return False
        
        # Se tem perito atribuído: só ele pode editar
        if ocorrencia.perito_atribuido:
            return user.id == ocorrencia.perito_atribuido.id
        
        # Se não tem perito: PERITO e OPERACIONAL do serviço podem editar
        return user.perfil in ['PERITO', 'OPERACIONAL']


class RelatorioPermission(BasePermission):
    """Permissão para relatórios (sempre read-only)"""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Apenas leitura
        if request.method not in ['GET', 'HEAD', 'OPTIONS']:
            return False
        
        # Todos os perfis podem ver relatórios
        return user.perfil in ['PERITO', 'OPERACIONAL', 'ADMINISTRATIVO'] or user.is_superuser