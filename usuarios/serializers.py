# usuarios/serializers.py

from rest_framework import serializers
from rest_framework.validators import UniqueValidator # <-- IMPORTE AQUI

from servicos_periciais.models import ServicoPericial
from servicos_periciais.serializers import ServicoPericialNestedSerializer
from .models import User

class UserCreateSerializer(serializers.ModelSerializer):
    # ... (código do serializer de criação permanece o mesmo) ...
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="Este endereço de e-mail já está em uso.")]
    )
    cpf = serializers.CharField(
        max_length=14,
        validators=[UniqueValidator(queryset=User.objects.all(), message="Este CPF já está cadastrado.")]
    )

    class Meta:
        model = User
        fields = [
            'nome_completo', 'email', 'data_nascimento', 'cpf',
            'telefone_celular', 'password'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'style': {'input_type': 'password'}, 'min_length': 6}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


# FAÇA AS MUDANÇAS NESTA CLASSE
class UserManagementSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="user-management-detail")

    # MUDANÇA PRINCIPAL AQUI:
    # Para LEITURA (quando exibe os dados), usa o serializer aninhado.
    servicos_periciais_info = ServicoPericialNestedSerializer(source='servicos_periciais', many=True, read_only=True)
    # Para ESCRITA (quando o admin seleciona na caixa), usa o campo de hyperlink.
    servicos_periciais = serializers.HyperlinkedRelatedField(
        many=True,
        queryset=ServicoPericial.objects.all(),
        view_name='servico-pericial-detail',
        write_only=True  # Este campo só será usado para escrita.
    )

    class Meta:
        model = User
        fields = [
            'url', 'id', 'nome_completo', 'email', 'cpf',
            'telefone_celular', 'data_nascimento', 'status', 'perfil',
            'servicos_periciais_info',  # Campo de leitura
            'servicos_periciais',  # Campo de escrita
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'nome_completo', 'email', 'cpf', 'telefone_celular',
            'data_nascimento', 'created_at', 'updated_at',
        ]