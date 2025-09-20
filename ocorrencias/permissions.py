# ocorrencias/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated
from usuarios.permissions import IsSuperAdminUser

class OcorrenciaPermission(BasePermission):
    """
    Permissão customizada para o modelo Ocorrencia:
    - Apenas perfis autorizados (não-administrativos) podem criar (POST).
    - O perfil Administrativo só pode visualizar (GET).
    - Apenas Super Admin pode deletar (DELETE).
    - Regras de edição são tratadas no serializer.
    """
    def has_permission(self, request, view):
        # Primeiro, garante que o usuário está logado
        if not IsAuthenticated().has_permission(request, view):
            return False

        # Se o método for de leitura (GET, HEAD, OPTIONS), todos os logados podem ver
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True

        # Se for para criar (POST), o perfil não pode ser ADMINISTRATIVO
        if request.method == 'POST':
            # Super Admin também não é ADMINISTRATIVO, então passa.
            return request.user.perfil != 'ADMINISTRATIVO'

        # Se for para editar (PUT/PATCH) ou deletar (DELETE), permite a princípio
        # para que a lógica mais específica na View ou Serializer possa agir.
        # A deleção será efetivamente barrada para não-Super Admins pelo Serializer/View se necessário.
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            # Vamos refinar a regra de DELETE aqui para ser explícita
            if request.method == 'DELETE':
                return IsSuperAdminUser().has_permission(request, view)
            return True # Permite PUT/PATCH para que a lógica do serializer decida

        return False


class PodeFinalizarOcorrencia(BasePermission):
    """
    Permite a ação de finalizar apenas para perfis Administrativo ou Super Admin.
    """
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (user.perfil in ['ADMINISTRATIVO', 'SUPER_ADMIN'])