# custodia/permissions.py

from rest_framework.permissions import BasePermission
from usuarios.models import User


def _is_externo(user):
    return user.perfil == User.Perfil.EXTERNO


class PodeCustodiar(BasePermission):
    """Escrita no módulo: todos os perfis internos exceto EXTERNO."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return not _is_externo(request.user)


class PodeVerCustodia(BasePermission):
    """Leitura: qualquer usuário autenticado e ativo."""
    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsExternoUser(BasePermission):
    """Dashboard exclusivo do perfil EXTERNO."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.perfil == User.Perfil.EXTERNO
        )


class IsCustodianteUser(BasePermission):
    """Dashboard exclusivo do perfil CUSTODIANTE."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.perfil == User.Perfil.CUSTODIANTE
        )


class PodeFinalizar(BasePermission):
    """
    Finalizar e reabrir vestígios: ADMINISTRATIVO, CUSTODIANTE e SUPER_ADMIN.

    PERITO e OPERACIONAL têm acesso ao módulo custódia mas não podem finalizar
    (ação irreversível de encerramento da cadeia de custódia, reservada a
    responsáveis com autoridade sobre o acervo físico).
    """
    message = 'Apenas administradores e custodiantes podem finalizar ou reabrir vestígios.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return (
            request.user.perfil in {
                User.Perfil.ADMINISTRATIVO,
                User.Perfil.CUSTODIANTE,
                User.Perfil.SUPER_ADMIN,
            }
            or request.user.is_superuser
        )


class IsSuperAdmin(BasePermission):
    """
    Deleção de registros forenses.

    Apenas SUPER_ADMIN (ou is_superuser Django) pode deletar vestígios,
    movimentações e DNAs. O sistema Java original não tinha DELETE nesses
    recursos — deleção é operação excepcional, restrita ao nível mais alto.
    """
    message = 'Apenas SUPER_ADMIN pode excluir registros forenses.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return (
            request.user.perfil == User.Perfil.SUPER_ADMIN
            or request.user.is_superuser
        )
