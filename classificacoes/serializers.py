# classificacoes/serializers.py

from rest_framework import serializers
from .models import ClassificacaoOcorrencia
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer # Importa para o 'deleted_by'

# -----------------------------------------------------------------------------
# SERIALIZER ANINHADO (JÁ ESTAVA CORRETO)
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassificacaoOcorrencia
        fields = ['id', 'codigo', 'nome']

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaSerializer(serializers.ModelSerializer):
    parent = ClassificacaoOcorrenciaNestedSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=ClassificacaoOcorrencia.objects.filter(parent__isnull=True),
        source='parent',
        write_only=True,
        required=False,
        allow_null=True,
        label='Grupo Pai'
    )
    codigo = serializers.CharField(
        max_length=20,
        validators=[UniqueValidator(queryset=ClassificacaoOcorrencia.objects.all(), message="Já existe uma classificação com este código.")]
    )
    nome = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(queryset=ClassificacaoOcorrencia.objects.all(), message="Já existe uma classificação com este nome.")]
    )

    class Meta:
        model = ClassificacaoOcorrencia
        # O campo 'url' foi removido
        fields = [
            'id',
            'codigo',
            'nome',
            'parent',
            'parent_id',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaLixeiraSerializer(serializers.ModelSerializer):
    parent = ClassificacaoOcorrenciaNestedSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = ClassificacaoOcorrencia
        # O campo 'url' foi removido
        fields = ['id', 'codigo', 'nome', 'parent', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']