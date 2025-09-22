# procedimentos/serializers.py

from rest_framework import serializers
from .models import Procedimento
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer # Importa para o 'deleted_by'

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ProcedimentoSerializer(serializers.ModelSerializer):
    sigla = serializers.CharField(
        max_length=20,
        validators=[UniqueValidator(queryset=Procedimento.objects.all(), message="Já existe um procedimento com esta sigla.")]
    )
    nome = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(queryset=Procedimento.objects.all(), message="Já existe um procedimento com este nome.")]
    )

    class Meta:
        model = Procedimento
        # O campo 'url' foi removido
        fields = ['id', 'sigla', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ProcedimentoLixeiraSerializer(serializers.ModelSerializer):
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Procedimento
        # O campo 'url' foi removido
        fields = ['id', 'sigla', 'nome', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']