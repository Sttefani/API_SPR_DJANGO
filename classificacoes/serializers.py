# classificacoes/serializers.py

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer
from .models import ClassificacaoOcorrencia

# -----------------------------------------------------------------------------
# SERIALIZER ANINHADO (PARA RELACIONAMENTOS)
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaNestedSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado usado para aninhar informações de classificação
    em outros serializers, como o campo 'parent'.
    """
    class Meta:
        model = ClassificacaoOcorrencia
        fields = ['id', 'codigo', 'nome']

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (PARA LISTAGEM, CRIAÇÃO E EDIÇÃO)
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaSerializer(serializers.ModelSerializer):
    """
    Serializer completo para gerenciar as classificações de ocorrência.
    Inclui todos os campos de auditoria e relacionamentos.
    """
    # Relacionamentos de leitura (para exibir dados aninhados no GET)
    parent = ClassificacaoOcorrenciaNestedSerializer(read_only=True)
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)

    # Campo de escrita para definir o 'parent' usando apenas o ID
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=ClassificacaoOcorrencia.objects.filter(parent__isnull=True),
        source='parent',
        write_only=True,
        required=False,
        allow_null=True,
        label='Grupo Pai'
    )

    # Validações de campos únicos
    codigo = serializers.CharField(
        max_length=20,
        validators=[UniqueValidator(
            queryset=ClassificacaoOcorrencia.objects.all(),
            message="Já existe uma classificação com este código."
        )]
    )
    nome = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(
            queryset=ClassificacaoOcorrencia.objects.all(),
            message="Já existe uma classificação com este nome."
        )]
    )

    class Meta:
        model = ClassificacaoOcorrencia
        fields = [
            'id',
            'codigo',
            'nome',
            'parent',
            'parent_id',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
        read_only_fields = [
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaLixeiraSerializer(serializers.ModelSerializer):
    """
    Serializer para a visualização da lixeira, mostrando quem e quando
    um item foi deletado (soft delete).
    """
    parent = ClassificacaoOcorrenciaNestedSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = ClassificacaoOcorrencia
        fields = [
            'id',
            'codigo',
            'nome',
            'parent',
            'deleted_at',
            'deleted_by'
        ]
        read_only_fields = [
            'deleted_at',
            'deleted_by'
        ]