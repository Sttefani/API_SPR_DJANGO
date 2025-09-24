# movimentacoes/permissions.py

from rest_framework.permissions import BasePermission
from ocorrencias.models import Ocorrencia


class MovimentacaoPermission(BasePermission):
    """
    Permissão customizada para o modelo Movimentacao.
    """
    message = "Você não tem permissão para executar esta ação."

    def get_ocorrencia(self, view):
        ocorrencia_id = view.kwargs.get('ocorrencia_pk')
        if not ocorrencia_id:
            return None
        try:
            return Ocorrencia.objects.select_related('perito_atribuido').get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            return None

    def has_permission(self, request, view):
        """
        Verifica a permissão para criar uma nova movimentação.
        """
        user = request.user
        if not user or not user.is_authenticated:
            self.message = "Autenticação necessária."
            return False

        ocorrencia = self.get_ocorrencia(view)
        if not ocorrencia:
            return False 

        if not ocorrencia.perito_atribuido:
            self.message = "Não é possível adicionar movimentações a uma ocorrência sem perito atribuído."
            return False

        # Super Admin e Administrativo sempre podem criar.
        if user.is_superuser or user.perfil == 'ADMINISTRATIVO':
            return True
        
        if user.perfil == 'PERITO':
            if user.id == ocorrencia.perito_atribuido.id:
                return True
            else:
                self.message = "Peritos só podem adicionar movimentações em ocorrências que lhes foram atribuídas."
                return False

        if user.perfil == 'OPERACIONAL':
            if user.servicos_periciais.filter(pk=ocorrencia.servico_pericial.pk).exists():
                return True
            else:
                self.message = "Servidores operacionais só podem adicionar movimentações em ocorrências do seu serviço pericial."
                return False

        return False

    def has_object_permission(self, request, view, obj):
        """
        Verifica a permissão em uma movimentação específica (para ver, editar ou deletar).
        """
        user = request.user
        ocorrencia = obj.ocorrencia

        # Super Admin pode fazer tudo.
        if user.is_superuser:
            return True

        # Apenas Super Admin pode deletar.
        if request.method == 'DELETE':
            self.message = "Apenas Super Administradores podem deletar movimentações."
            return False

        # AQUI ESTÁ A MUDANÇA: Servidor ADMINISTRATIVO pode ver e editar.
        if user.perfil == 'ADMINISTRATIVO':
            return True # Permite GET, PUT, PATCH
        
        # PERITO só pode editar movimentações das suas ocorrências.
        if user.perfil == 'PERITO':
            if user.id == ocorrencia.perito_atribuido.id:
                return True
            else:
                self.message = "Peritos só podem editar movimentações de suas próprias ocorrências."
                return False

        # SERVIDOR OPERACIONAL pode editar movimentações de ocorrências do seu serviço.
        if user.perfil == 'OPERACIONAL':
            if user.servicos_periciais.filter(pk=ocorrencia.servico_pericial.pk).exists():
                return True
            else:
                self.message = "Servidores operacionais só podem editar movimentações de ocorrências do seu serviço."
                return False

        # Nega qualquer outra tentativa.
        return False