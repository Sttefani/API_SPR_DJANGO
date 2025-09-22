# unidades_demandantes/serializers.py

from rest_framework import serializers
from .models import UnidadeDemandante
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer 

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class UnidadeDemandanteSerializer(serializers.ModelSerializer):
    sigla = serializers.CharField(
        max_length=20,
        validators=[UniqueValidator(queryset=UnidadeDemandante.objects.all(), message="Já existe uma unidade com esta sigla.")]
    )
    nome = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(queryset=UnidadeDemandante.objects.all(), message="Já existe uma unidade com este nome.")]
    )

    class Meta:
        model = UnidadeDemandante
        # O campo 'url' foi removido
        fields = ['id', 'sigla', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class UnidadeDemandanteLixeiraSerializer(serializers.ModelSerializer):
    # Mostra os detalhes do usuário que deletou
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = UnidadeDemandante
        # O campo 'url' foi removido
        fields = ['id', 'sigla', 'nome', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']