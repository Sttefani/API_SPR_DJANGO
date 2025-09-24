# ordens_servico/permissions.py

from rest_framework.permissions import BasePermission

class OrdemServicoPermission(BasePermission):
    """
    Permissão customizada para o modelo OrdemServico, com regras
    específicas baseadas no perfil e na ação.
    """
    message = "Você não tem permissão para executar esta ação."

    def has_permission(self, request, view):
        """
        Verifica a permissão para ações de nível de coleção (como listar e criar).
        """
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # REGRA: Apenas ADMIN e SUPER_ADMIN podem criar uma nova Ordem de Serviço.
        if view.action == 'create':
            return user.perfil in ['ADMINISTRATIVO', 'SUPER_ADMIN']
        
        # Para listar (GET), a permissão é concedida. A filtragem (quem vê o quê)
        # será feita na própria ViewSet, no método get_queryset.
        return True

    def has_object_permission(self, request, view, obj):
        """
        Verifica a permissão em uma Ordem de Serviço específica (ver detalhes, editar, deletar).
        'obj' é a instância da OrdemServico.
        """
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # REGRA: Super Admin pode fazer tudo em qualquer OS.
        if user.is_superuser:
            return True

        # Pega o perito a quem a OS se destina (através da ocorrência pai)
        perito_destinatario = obj.ocorrencia.perito_atribuido

        # REGRA: Apenas Super Admin pode deletar.
        if view.action == 'destroy':
            return False # Já foi coberto pela checagem de is_superuser

        # REGRA: Servidor ADMINISTRATIVO pode editar e concluir.
        if user.perfil == 'ADMINISTRATIVO':
            if view.action in ['update', 'partial_update', 'concluir']:
                return True

        # REGRA: O Perito destinatário pode visualizar e tomar ciência.
        if user.perfil == 'PERITO':
            # Verifica se o perito logado é o destinatário da OS
            if perito_destinatario and user.id == perito_destinatario.id:
                # Permite apenas as ações de visualização e de tomar ciência
                if view.action in ['retrieve', 'tomar_ciencia']:
                    return True
        
        # Se nenhuma das regras acima se aplicou, nega a permissão.
        return False