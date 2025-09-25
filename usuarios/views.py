# usuarios/views.py

from rest_framework import viewsets, mixins

from usuarios.pdf_generator import gerar_pdf_listagem_usuarios, gerar_pdf_usuarios_por_perfil
from .models import User
from .serializers import UserCreateSerializer, UserManagementSerializer
from .permissions import IsSuperAdminUser
from rest_framework.decorators import action          # <-- ADICIONE ESTA LINHA SE NÃO TIVER


class UserRegistrationViewSet(mixins.CreateModelMixin,
                              viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer


class UserManagementViewSet(mixins.ListModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin,
                            mixins.DestroyModelMixin,  # <-- ADICIONE O MIXIN DE DELEÇÃO
                            viewsets.GenericViewSet):
    """
    Endpoint da API para Super Admins gerenciarem usuários.
    Permite listar, ver detalhes, atualizar e deletar (soft delete).
    """
    queryset = User.objects.filter(is_superuser=False).order_by('-created_at')
    serializer_class = UserManagementSerializer
    permission_classes = [IsSuperAdminUser]
    filterset_fields = ['nome_completo', 'email', 'cpf', 'status', 'perfil']


    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    # ADICIONE ESTE MÉTODO PARA IMPLEMENTAR O SOFT DELETE
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Chama o nosso método customizado do modelo
        instance.soft_delete(user=request.user)
        # Preenche o campo 'deleted_by'
        instance.deleted_by = request.user
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    # ADICIONE SÓ ESTES 3 MÉTODOS NO FINAL:
    @action(detail=True, methods=['get'], url_path='pdf')
    def gerar_pdf(self, request, *args, **kwargs):
        usuario = self.get_object()
        return gerar_pdf_usuario(usuario, request)

    @action(detail=False, methods=['get'], url_path='listagem-pdf')
    def gerar_listagem_pdf(self, request, *args, **kwargs):
        return gerar_pdf_listagem_usuarios(request)

    @action(detail=False, methods=['get'], url_path='perfil-pdf/(?P<perfil>[^/.]+)')
    def gerar_perfil_pdf(self, request, perfil=None, *args, **kwargs):
        perfis_validos = [choice[0] for choice in User.Perfil.choices]
        if perfil not in perfis_validos:
            return Response(
                {"error": f"Perfil inválido. Opções: {', '.join(perfis_validos)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        return gerar_pdf_usuarios_por_perfil(perfil, request)