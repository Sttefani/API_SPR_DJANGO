# usuarios/views.py

from rest_framework import viewsets, mixins
from .models import User
from .serializers import UserCreateSerializer, UserManagementSerializer
from .permissions import IsSuperAdminUser

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