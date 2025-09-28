# usuarios/views.py

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import IsSuperAdminUser
from .serializers import (
    UserCreateSerializer,
    UserManagementSerializer,
    ChangePasswordSerializer,
    MyTokenObtainPairSerializer
)


class UserRegistrationViewSet(mixins.CreateModelMixin,
                              viewsets.GenericViewSet):
    """
    Endpoint para que novos usuários possam se registrar.
    Cria um usuário com status 'PENDENTE'.
    """
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer


class UserManagementViewSet(mixins.ListModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin,
                            mixins.DestroyModelMixin,
                            viewsets.GenericViewSet):
    """
    Endpoint para Super Admins gerenciarem todos os outros usuários.
    """
    queryset = User.objects.filter(is_superuser=False).order_by('-created_at')
    serializer_class = UserManagementSerializer
    permission_classes = [IsSuperAdminUser]
    filterset_fields = ['nome_completo', 'email', 'cpf', 'status', 'perfil']

    def perform_update(self, serializer):
        """Salva quem foi o último a atualizar o usuário."""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Executa o soft delete em vez da exclusão real do banco de dados."""
        instance.soft_delete(user=self.request.user)

    # =============================================================================
    # AÇÃO PARA RESETAR A SENHA DE UM USUÁRIO PARA SEU CPF
    # =============================================================================
    @action(detail=True, methods=['post'], url_path='resetar-senha-cpf')
    def reset_password_to_cpf(self, request, pk=None):
        """
        Reseta a senha do usuário para o seu CPF (sem pontos ou traços)
        e o força a alterar a senha no próximo login.
        """
        user = self.get_object()

        if not user.cpf:
            return Response(
                {'error': 'Usuário não possui CPF cadastrado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Remove caracteres não numéricos do CPF para usar como senha
        cpf_como_senha = ''.join(filter(str.isdigit, user.cpf))

        # Define a nova senha e a flag de alteração obrigatória
        user.set_password(cpf_como_senha)
        user.deve_alterar_senha = True
        user.updated_by = request.user
        user.save()

        return Response(
            {'status': f'Senha do usuário {user.nome_completo} foi redefinida para seu CPF.'},
            status=status.HTTP_200_OK
        )


class ChangePasswordView(APIView):
    """
    Endpoint para um usuário LOGADO alterar sua PRÓPRIA senha.
    Usado na tela de troca de senha obrigatória.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            old_password = serializer.validated_data['old_password']
            new_password = serializer.validated_data['new_password']

            # Verifica se a senha antiga (o CPF, por exemplo) está correta
            if not user.check_password(old_password):
                return Response({"error": "A senha antiga está incorreta."}, status=status.HTTP_400_BAD_REQUEST)

            # Define a nova senha e desmarca a flag de alteração obrigatória
            user.set_password(new_password)
            user.deve_alterar_senha = False
            user.save()
            
            return Response({"status": "Senha alterada com sucesso."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyTokenObtainPairView(TokenObtainPairView):
    """
    Substitui a view de login padrão para incluir o campo 'deve_alterar_senha'
    na resposta do token.
    """
    serializer_class = MyTokenObtainPairSerializer