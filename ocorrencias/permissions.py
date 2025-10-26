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
    """
    message = "Você não tem permissão para realizar esta ação."
    
    def has_permission(self, request, view):
        # Barreira 1: Precisa estar logado para qualquer ação
        if not IsAuthenticated().has_permission(request, view):
            return False

        # Barreira 2: Apenas Super Admin pode deletar
        if request.method == 'DELETE':
            return IsSuperAdminUser().has_permission(request, view)
        
        # Barreira 3: O perfil ADMINISTRATIVO não pode criar
        if request.method == 'POST':
            if request.user.perfil == 'ADMINISTRATIVO':
                self.message = (
                    "❌ Operação não permitida: Usuários com perfil ADMINISTRATIVO não podem "
                    "criar novas ocorrências. Apenas perfis PERITO, OPERACIONAL ou SUPER_ADMIN "
                    "têm permissão para registrar ocorrências no sistema."
                )
                return False
            return True

        # Permite outras ações como GET, PUT, PATCH
        return True


class PodeFinalizarOcorrencia(BasePermission):
    """
    Permite a ação de finalizar apenas para perfis Administrativo ou Super Admin.
    """
    message = (
        "🔒 Acesso Restrito: Apenas usuários com perfil ADMINISTRATIVO ou SUPER_ADMIN "
        "podem finalizar ocorrências. Esta é uma operação crítica que requer "
        "autorização específica."
    )
    
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (user.perfil in ['ADMINISTRATIVO', 'SUPER_ADMIN'])


class PodeReabrirOcorrencia(BasePermission):
    """
    Permite a ação de reabrir apenas para Super Admin.
    """
    message = (
        "🔒 Acesso Restrito: Apenas Super Administradores podem reabrir ocorrências finalizadas. "
        "Esta é uma operação crítica que afeta a integridade dos dados e auditoria. "
        "Entre em contato com um Super Admin se precisar reabrir uma ocorrência."
    )
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser


class PodeEditarOcorrencia(BasePermission):
    """
    Permissão específica para edição baseada no objeto.
    
    REGRAS DE NEGÓCIO:
    1. Finalizada: NINGUÉM pode editar (nem super admin) - precisa REABRIR primeiro
    2. Com perito atribuído: apenas o perito atribuído ou super admin podem editar
    3. Sem perito: PERITO, OPERACIONAL e ADMINISTRATIVO podem editar
    """
    message = "Você não tem permissão para editar esta ocorrência."
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # ⛔ REGRA 1: NINGUÉM EDITA FINALIZADA (NEM SUPER ADMIN)
        # Para editar, é necessário REABRIR a ocorrência primeiro
        if obj.esta_finalizada:
            self.message = (
                "❌ Operação Bloqueada: Esta ocorrência está FINALIZADA e não pode ser editada. "
                "Para realizar alterações, é necessário reabrir a ocorrência primeiro. "
                f"Finalizada por: {obj.finalizada_por.nome_completo if obj.finalizada_por else 'N/A'} "
                f"em {obj.data_finalizacao.strftime('%d/%m/%Y às %H:%M') if obj.data_finalizacao else 'N/A'}. "
                "Apenas Super Administradores podem reabrir ocorrências."
            )
            return False
        
        # ✅ Super Admin pode editar qualquer ocorrência NÃO finalizada
        if user.is_superuser:
            return True
        
        # 🔒 REGRA 2: Se TEM perito atribuído, só o perito pode editar
        if obj.perito_atribuido:
            if user.id == obj.perito_atribuido.id:
                return True
            
            self.message = (
                f"🔒 Acesso Restrito: Esta ocorrência está atribuída ao perito "
                f"{obj.perito_atribuido.nome_completo}. "
                "Apenas o perito atribuído ou um Super Administrador podem editar esta ocorrência. "
                "Se necessário, solicite que o perito atribuído faça a alteração ou contate "
                "um administrador do sistema."
            )
            return False
        
        # ✅ REGRA 3: Se NÃO TEM perito, permite edição para perfis autorizados
        if user.perfil in ['PERITO', 'OPERACIONAL', 'ADMINISTRATIVO']:
            return True
        
        self.message = (
            "❌ Acesso Negado: Seu perfil de usuário não tem permissão para editar ocorrências. "
            "Entre em contato com um administrador se precisar de acesso."
        )
        return False
    
    
class PeritoAtribuidoRequired(BasePermission):
    """
    Permissão que verifica se a ocorrência já tem um perito atribuído.
    Usado para gerenciamento de exames.
    """
    message = (
        "⚠️ Ação Bloqueada: É necessário atribuir um perito à ocorrência antes de gerenciar os exames. "
        "Por favor, atribua um perito responsável primeiro e tente novamente."
    )

    def has_object_permission(self, request, view, obj):
        return obj.perito_atribuido is not None
    
    
class PodeVerRelatoriosGerenciais(BasePermission):
    """
    Permite o acesso a relatórios e estatísticas gerenciais apenas para perfis
    ADMINISTRATIVO ou Super Admin.
    """
    message = (
        "🔒 Acesso Restrito: Você não tem permissão para acessar informações gerenciais. "
        "Apenas usuários com perfil ADMINISTRATIVO ou SUPER_ADMIN têm acesso a relatórios, "
        "estatísticas e painéis gerenciais. Entre em contato com um administrador se precisar "
        "deste tipo de acesso."
    )

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.is_superuser or request.user.perfil == 'ADMINISTRATIVO'