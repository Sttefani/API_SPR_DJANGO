# usuarios/serializers.py

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User
from servicos_periciais.models import ServicoPericial

# -----------------------------------------------------------------------------
# SERIALIZER ANINHADO SIMPLES PARA SERVIÇOS (PARA USO INTERNO)
# -----------------------------------------------------------------------------
class ServicoPericialNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicoPericial
        fields = ['id', 'sigla', 'nome']


# -----------------------------------------------------------------------------
# SERIALIZER PARA CRIAÇÃO DE NOVOS USUÁRIOS (CADASTRO)
# -----------------------------------------------------------------------------
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
        # O status padrão 'PENDENTE' e deve_alterar_senha=False são definidos no modelo
        user.save()
        return user


# -----------------------------------------------------------------------------
# SERIALIZER PARA GERENCIAMENTO DE USUÁRIOS (TELA DO SUPER ADMIN)
# -----------------------------------------------------------------------------
class UserManagementSerializer(serializers.ModelSerializer):
    # Para LEITURA: Mostra os detalhes dos serviços.
    servicos_periciais = ServicoPericialNestedSerializer(many=True, read_only=True)
    
    # Para ESCRITA: Espera uma lista de IDs de serviços.
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
            'deve_alterar_senha',  # CAMPO ADICIONADO PARA VISIBILIDADE DO ADMIN
            'servicos_periciais',
            'servicos_periciais_ids',
            'created_at', 'updated_at',
        ]
        # Campos que o admin não pode alterar diretamente por esta tela
        read_only_fields = [
            'id', 'nome_completo', 'email', 'cpf', 'telefone_celular',
            'data_nascimento', 'created_at', 'updated_at', 'deve_alterar_senha'
        ]


# -----------------------------------------------------------------------------
# SERIALIZER "LEVE" PARA ANINHAMENTO EM OUTROS MODELOS
# -----------------------------------------------------------------------------
class UserNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nome_completo', 'email']


# =============================================================================
# SERIALIZERS PARA A NOVA FUNCIONALIDADE DE RESET/CHANGE DE SENHA
# =============================================================================

# 1. Para o login (Token), para informar o frontend sobre a necessidade de troca
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Adiciona dados customizados ao payload do token
        token['nome_completo'] = user.nome_completo
        token['perfil'] = user.perfil
        token['deve_alterar_senha'] = user.deve_alterar_senha

        return token


# 2. Para o endpoint onde o próprio usuário vai alterar sua senha
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, min_length=6, write_only=True)