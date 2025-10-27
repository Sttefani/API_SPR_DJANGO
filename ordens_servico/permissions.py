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
            self.message = "Autenticação necessária."
            return False

        # REGRA: Apenas ADMIN e SUPER_ADMIN podem criar OS ou reiterar
        if view.action in ["create", "reiterar"]:
            if user.perfil in ["ADMINISTRATIVO", "SUPER_ADMIN"]:
                return True
            self.message = (
                "Apenas administrativos podem criar/reiterar Ordens de Serviço."
            )
            return False

        # Para outras actions, a permissão será verificada no has_object_permission
        return True

    def has_object_permission(self, request, view, obj):
        """
        Verifica a permissão em uma Ordem de Serviço específica.
        """
        user = request.user
        if not user or not user.is_authenticated:
            self.message = "Autenticação necessária."
            return False

        # REGRA: Super Admin pode fazer TUDO
        if user.is_superuser:
            return True

        # Pega o perito destinatário da OS
        perito_destinatario = obj.ocorrencia.perito_atribuido

        # =====================================================================
        # ACTIONS DO ADMINISTRATIVO
        # =====================================================================
        if view.action in [
            "update",
            "partial_update",
            "concluir",
            "reiterar",
            "restaurar",
        ]:
            if user.perfil == "ADMINISTRATIVO":
                return True
            self.message = "Apenas administrativos podem executar esta ação."
            return False

        # =====================================================================
        # DELETAR - SÓ SUPER ADMIN
        # =====================================================================
        if view.action == "destroy":
            self.message = (
                "Apenas Super Administradores podem deletar Ordens de Serviço."
            )
            return False

        # =====================================================================
        # ACTIONS DO PERITO (destinatário)
        # =====================================================================
        if view.action in ["tomar_ciencia", "iniciar_trabalho", "justificar_atraso"]:
            # Verifica se o usuário é o perito destinatário
            if user.perfil == "PERITO":
                if perito_destinatario and user.id == perito_destinatario.id:
                    return True
                self.message = "Apenas o perito designado pode executar esta ação."
                return False
            self.message = "Apenas peritos podem executar esta ação."
            return False

        # =====================================================================
        # VISUALIZAR E GERAR PDFs
        # =====================================================================
        if view.action in ["retrieve", "gerar_pdf", "gerar_pdf_oficial"]:
            # ADMINISTRATIVO pode ver todas
            if user.perfil == "ADMINISTRATIVO":
                return True

            # PERITO só pode ver as suas
            if user.perfil == "PERITO":
                if perito_destinatario and user.id == perito_destinatario.id:
                    return True
                self.message = (
                    "Você só pode visualizar suas próprias Ordens de Serviço."
                )
                return False

        # =====================================================================
        # LISTAGEM DE PDF
        # =====================================================================
        if view.action == "gerar_listagem_pdf":
            # Qualquer um com acesso à ocorrência pode gerar listagem
            return True

        # Se nenhuma regra se aplicou, nega
        self.message = "Você não tem permissão para executar esta ação."
        return False
