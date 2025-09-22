# servicos_periciais/serializers.py

from rest_framework import serializers
from .models import ServicoPericial
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer # Importa para o 'deleted_by'

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (JÁ ESTAVA CORRETO)
# -----------------------------------------------------------------------------
class ServicoPericialSerializer(serializers.ModelSerializer):
    sigla = serializers.CharField(
        max_length=10,
        validators=[UniqueValidator(queryset=ServicoPericial.objects.all(), message="Já existe um serviço com esta sigla.")]
    )
    nome = serializers.CharField(
        max_length=50,
        validators=[UniqueValidator(queryset=ServicoPericial.objects.all(), message="Já existe um serviço com este nome.")]
    )

    class Meta:
        model = ServicoPericial
        fields = ['id', 'sigla', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (COM 'deleted_by' ADICIONADO)
# -----------------------------------------------------------------------------
class ServicoPericialLixeiraSerializer(serializers.ModelSerializer):
    # Mostra os detalhes do usuário que deletou
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = ServicoPericial
        fields = ['id', 'sigla', 'nome', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']

# -----------------------------------------------------------------------------
# SERIALIZER ANINHADO (JÁ ESTAVA CORRETO)
# -----------------------------------------------------------------------------
class ServicoPericialNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicoPericial
        fields = ['id', 'sigla', 'nome']