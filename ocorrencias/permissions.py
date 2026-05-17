# ocorrencias/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated
from usuarios.permissions import IsSuperAdminUser


class OcorrenciaPermission(BasePermission):
    """
    Permissão principal para a OcorrenciaViewSet.

    REGRAS:
    - Precisa estar autenticado para qualquer ação
    - Apenas Super Admin pode deletar
    - ADMINISTRATIVO não pode criar ocorrências
    - ADMINISTRATIVO pode vincular/desvincular procedimentos
    """

    message = "Você não tem permissão para realizar esta ação."

    def has_permission(self, request, view):
        if not IsAuthenticated().has_permission(request, view):
            return False

        if request.method == "DELETE":
            return IsSuperAdminUser().has_permission(request, view)

        if request.method == "POST":
            if request.user.perfil == "ADMINISTRATIVO":
                if view.action == "vincular_procedimento":
                    return True
                self.message = (
                    "❌ Operação não permitida: Usuários com perfil ADMINISTRATIVO não podem "
                    "criar novas ocorrências. Apenas perfis PERITO, OPERACIONAL ou SUPER_ADMIN "
                    "têm permissão para registrar ocorrências no sistema."
                )
                return False
            return True

        return True


class PodeFinalizarOcorrencia(BasePermission):
    """
    Permite finalizar apenas para ADMINISTRATIVO ou SUPER_ADMIN.
    """

    message = (
        "🔒 Acesso Restrito: Apenas usuários com perfil ADMINISTRATIVO ou SUPER_ADMIN "
        "podem finalizar ocorrências."
    )

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (
            user.perfil in ["ADMINISTRATIVO", "SUPER_ADMIN"]
        )


class PodeReabrirOcorrencia(BasePermission):
    """
    Permite reabrir apenas para Super Admin.
    """

    message = (
        "🔒 Acesso Restrito: Apenas Super Administradores podem reabrir ocorrências finalizadas."
    )

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser


class PodeEntregarLaudo(BasePermission):
    """
    Permite registrar entrega do laudo apenas para o perito atribuído ou Super Admin.
    Validação do perito atribuído é feita na view (precisa do objeto).
    """

    message = (
        "🔒 Acesso Restrito: Apenas o perito atribuído à ocorrência ou um SUPER_ADMIN "
        "pode registrar a entrega do laudo."
    )

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (
            user.perfil in ["PERITO", "SUPER_ADMIN"] or user.is_superuser
        )


class PodeReverterLaudo(BasePermission):
    """
    Permite reverter LAUDO_ENTREGUE → EM_ANALISE para ADMINISTRATIVO ou SUPER_ADMIN.
    """

    message = (
        "🔒 Acesso Restrito: Apenas usuários com perfil ADMINISTRATIVO ou SUPER_ADMIN "
        "podem reverter a entrega do laudo."
    )

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (
            user.perfil in ["ADMINISTRATIVO", "SUPER_ADMIN"] or user.is_superuser
        )


class PodeEditarOcorrencia(BasePermission):
    """
    Permissão específica para edição baseada no objeto.

    REGRAS DE NEGÓCIO:
    1. Finalizada: NINGUÉM pode editar — precisa REABRIR primeiro
    2. Com perito atribuído: apenas o perito atribuído ou super admin podem editar
    3. Sem perito: PERITO, OPERACIONAL e ADMINISTRATIVO podem editar
    """

    message = "Você não tem permissão para editar esta ocorrência."

    def has_object_permission(self, request, view, obj):
        user = request.user

        if obj.esta_finalizada:
            self.message = (
                "❌ Operação Bloqueada: Esta ocorrência está FINALIZADA e não pode ser editada. "
                "Para realizar alterações, é necessário reabrir a ocorrência primeiro. "
                f"Finalizada por: {obj.finalizada_por.nome_completo if obj.finalizada_por else 'N/A'} "
                f"em {obj.data_finalizacao.strftime('%d/%m/%Y às %H:%M') if obj.data_finalizacao else 'N/A'}. "
                "Apenas Super Administradores podem reabrir ocorrências."
            )
            return False

        if user.is_superuser:
            return True

        if obj.perito_atribuido:
            if user.id == obj.perito_atribuido.id:
                return True
            self.message = (
                f"🔒 Acesso Restrito: Esta ocorrência está atribuída ao perito "
                f"{obj.perito_atribuido.nome_completo}. "
                "Apenas o perito atribuído ou um Super Administrador podem editar esta ocorrência."
            )
            return False

        if user.perfil in ["PERITO", "OPERACIONAL", "ADMINISTRATIVO"]:
            return True

        self.message = (
            "❌ Acesso Negado: Seu perfil de usuário não tem permissão para editar ocorrências."
        )
        return False


class PeritoAtribuidoRequired(BasePermission):
    """
    Verifica se a ocorrência tem perito atribuído antes de gerenciar exames.
    """

    message = (
        "⚠️ Ação Bloqueada: É necessário atribuir um perito à ocorrência antes de gerenciar os exames."
    )

    def has_object_permission(self, request, view, obj):
        return obj.perito_atribuido is not None


class PodeVerRelatoriosGerenciais(BasePermission):
    """
    Acesso a relatórios e estatísticas gerenciais apenas para ADMINISTRATIVO ou Super Admin.
    """

    message = (
        "🔒 Acesso Restrito: Apenas usuários com perfil ADMINISTRATIVO ou SUPER_ADMIN "
        "têm acesso a relatórios e painéis gerenciais."
    )

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.perfil == "ADMINISTRATIVO"
