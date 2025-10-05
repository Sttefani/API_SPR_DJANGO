# usuarios/serializers.py

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User
from servicos_periciais.models import ServicoPericial

User = get_user_model()


# -----------------------------------------------------------------------------
# NENHUMA ALTERAÇÃO NOS SERIALIZERS ABAIXO
# -----------------------------------------------------------------------------
class ServicoPericialNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicoPericial
        fields = ['id', 'sigla', 'nome']

class UserCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="Este endereço de e-mail já está em uso.")]
    )
    cpf = serializers.CharField(
        max_length=14,
        validators=[UniqueValidator(queryset=User.objects.all(), message="Este CPF já está cadastrado.")]
    )
    class Meta:
        model = User
        fields = ['nome_completo', 'email', 'data_nascimento', 'cpf', 'telefone_celular', 'password']
        extra_kwargs = {
            'password': {'write_only': True, 'style': {'input_type': 'password'}, 'min_length': 6}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class UserManagementSerializer(serializers.ModelSerializer):
    servicos_periciais = ServicoPericialNestedSerializer(many=True, read_only=True)
    servicos_periciais_ids = serializers.PrimaryKeyRelatedField(
        queryset=ServicoPericial.objects.all(),
        source='servicos_periciais',
        many=True,
        write_only=True,
        label='Serviços Periciais'
    )
    class Meta:
        model = User
        fields = [
            'id', 'nome_completo', 'email', 'cpf',
            'telefone_celular', 'data_nascimento', 'status', 'perfil',
            'deve_alterar_senha',
            'servicos_periciais',
            'servicos_periciais_ids',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'nome_completo', 'email', 'cpf',
            'data_nascimento', 'created_at', 'updated_at', 'deve_alterar_senha'
        ]

class UserNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nome_completo', 'email']

# =============================================================================
# CORREÇÃO APLICADA AQUI
# =============================================================================
# usuarios/serializers.py

# ... (todos os outros imports e serializers que não serão alterados) ...

# =============================================================================
# CORREÇÃO FINAL APLICADA AQUI
# =============================================================================
# ... (imports e outros serializers continuam os mesmos) ...

# =============================================================================
# VERSÃO DE TESTE - LÓGICA MANUAL E DIRETA
# =============================================================================
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['nome_completo'] = user.nome_completo
        token['perfil'] = user.perfil
        token['deve_alterar_senha'] = user.deve_alterar_senha
        token['is_superuser'] = user.is_superuser
        
        # ← ADICIONAR: Serializar os serviços periciais
        token['servicos_periciais'] = [
            {
                'id': s.id,
                'sigla': s.sigla,
                'nome': s.nome
            }
            for s in user.servicos_periciais.all()
        ]
        
        return token
    
    def validate(self, attrs):
        email = attrs.get(self.username_field)
        password = attrs.get("password")
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed("E-mail ou senha incorretos.")
        
        if user.status == User.Status.PENDENTE:
            raise AuthenticationFailed("Seu cadastro ainda está pendente de aprovação.")
       
        if user.status == User.Status.INATIVO:
            raise AuthenticationFailed("Sua conta está inativa. Entre em contato com o suporte.")
        
        if not user.check_password(password):
            raise AuthenticationFailed("E-mail ou senha incorretos.")
        
        data = super().validate(attrs)
       
        # ← ADICIONAR: Incluir servicos_periciais na resposta também
        data['user'] = {
            'id': self.user.id,
            'nome_completo': self.user.nome_completo,
            'email': self.user.email,
            'perfil': self.user.perfil,
            'deve_alterar_senha': self.user.deve_alterar_senha,
            'is_superuser': self.user.is_superuser,
            'servicos_periciais': [
                {
                    'id': s.id,
                    'sigla': s.sigla,
                    'nome': s.nome
                }
                for s in self.user.servicos_periciais.all()
            ]
        }
       
        return data
# -----------------------------------------------------------------------------
# NENHUMA ALTERAÇÃO AQUI
# -----------------------------------------------------------------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, min_length=6, write_only=True)