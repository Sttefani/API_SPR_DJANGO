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
    
    def update(self, request, *args, **kwargs):
        """Override para debug"""
        print("=" * 80)
        print(f"🔍 DADOS RECEBIDOS: {request.data}")
        print("=" * 80)
        
        try:
            response = super().update(request, *args, **kwargs)
            print("✅ Sucesso!")
            return response
        except Exception as e:
            print(f"❌ ERRO: {type(e).__name__}")
            print(f"❌ MENSAGEM: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def partial_update(self, request, *args, **kwargs):
        """Override para debug"""  
        print("=" * 80)
        print(f"🔍 PARTIAL UPDATE - DADOS: {request.data}")
        print("=" * 80)
        
        try:
            response = super().partial_update(request, *args, **kwargs)
            print("✅ Sucesso!")
            return response
        except Exception as e:
            print(f"❌ ERRO: {type(e).__name__}")
            print(f"❌ MENSAGEM: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def perform_update(self, serializer):
        """Salva quem foi o último a atualizar o usuário."""
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        """Salva quem foi o último a atualizar o usuário."""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Executa o soft delete em vez da exclusão real do banco de dados."""
        instance.soft_delete(user=self.request.user)

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

        cpf_como_senha = ''.join(filter(str.isdigit, user.cpf))
        user.set_password(cpf_como_senha)
        user.deve_alterar_senha = True
        user.updated_by = request.user
        user.save()

        return Response(
            {'status': f'Senha do usuário {user.nome_completo} foi redefinida para seu CPF.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='aprovar')
    def approve_user(self, request, pk=None):
        """
        Muda o status de um usuário de 'PENDENTE' para 'ATIVO'.
        """
        user = self.get_object()

        if user.status != User.Status.PENDENTE:
            return Response(
                {'error': 'Este usuário não está pendente de aprovação.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.status = User.Status.ATIVO
        user.updated_by = request.user
        user.save(update_fields=['status', 'updated_by', 'updated_at'])

        return Response(
            {'status': f'Usuário {user.nome_completo} aprovado com sucesso.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='reprovar')
    def reject_user(self, request, pk=None):
        """
        Muda o status de um usuário de 'PENDENTE' para 'INATIVO'.
        """
        user = self.get_object()

        if user.status != User.Status.PENDENTE:
            return Response(
                {'error': 'Este usuário não está pendente de aprovação.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.status = User.Status.INATIVO
        user.updated_by = request.user
        user.save(update_fields=['status', 'updated_by', 'updated_at'])

        return Response(
            {'status': f'Cadastro do usuário {user.nome_completo} foi reprovado.'},
            status=status.HTTP_200_OK
        )
        
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def peritos_dropdown(self, request):
        """Lista simplificada de peritos para dropdowns"""
        peritos = User.objects.filter(
            perfil='PERITO', 
            deleted_at__isnull=True
        ).order_by('nome_completo')
        
        data = [
            {
                'id': perito.id,
                'nome_completo': perito.nome_completo
            }
            for perito in peritos
        ]
        return Response(data)
                
    @action(detail=False, methods=['get'])
    def dropdown(self, request):
        """Retorna TODOS os usuários ATIVOS para uso em dropdowns (sem paginação)"""
        queryset = User.objects.filter(status='ATIVO').order_by('nome_completo')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
        
    @action(detail=True, methods=['post'], url_path='reativar')
    def reactivate_user(self, request, pk=None):
        """
        Muda status de INATIVO para PENDENTE
        """
        user = self.get_object()
        
        if user.status != User.Status.INATIVO:
            return Response(
                {'error': 'Apenas usuários inativos podem ser reativados.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.status = User.Status.PENDENTE
        user.updated_by = request.user
        user.save(update_fields=['status', 'updated_by', 'updated_at'])
        
        return Response(
            {'status': f'Usuário {user.nome_completo} reativado para aprovação.'},
            status=status.HTTP_200_OK
        )


class ChangePasswordView(APIView):
    """
    Endpoint para um usuário LOGADO alterar sua PRÓPRIA senha.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            old_password = serializer.validated_data['old_password']
            new_password = serializer.validated_data['new_password']

            if not user.check_password(old_password):
                return Response(
                    {"error": "A senha antiga está incorreta."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.set_password(new_password)
            user.deve_alterar_senha = False
            user.save()
            
            return Response(
                {"status": "Senha alterada com sucesso."}, 
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyTokenObtainPairView(TokenObtainPairView):
    """
    Substitui a view de login padrão para incluir campos customizados.
    """
    serializer_class = MyTokenObtainPairSerializer