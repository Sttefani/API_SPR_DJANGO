# tipos_documento/serializers.py

from rest_framework import serializers
from .models import TipoDocumento
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer # Importa para o 'deleted_by'

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class TipoDocumentoSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(queryset=TipoDocumento.objects.all(), message="Já existe um tipo de documento com este nome.")]
    )
    class Meta:
        model = TipoDocumento
        # O campo 'url' foi removido
        fields = ['id', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class TipoDocumentoLixeiraSerializer(serializers.ModelSerializer):
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = TipoDocumento
        # O campo 'url' foi removido
        fields = ['id', 'nome', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']