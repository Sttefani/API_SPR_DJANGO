# classificacoes/serializers.py

from rest_framework import serializers
from .models import ClassificacaoOcorrencia
from rest_framework.validators import UniqueValidator

# -----------------------------------------------------------------------------
# Serializer "miniatura" para aninhamento (mostrar detalhes do pai)
# Ele é usado para exibir as informações do "parent" de forma legível.
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassificacaoOcorrencia
        fields = ['id', 'codigo', 'nome']

# -----------------------------------------------------------------------------
# Serializer principal, usado para criar, editar e ver os detalhes.
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="classificacaoocorrencia-detail")

    # Para LEITURA: Mostra os detalhes do grupo pai usando o serializer aninhado.
    parent = ClassificacaoOcorrenciaNestedSerializer(read_only=True)

    # Para ESCRITA: Cria um campo 'parent_id' que só aceita IDs de grupos principais.
    # Este campo gera o <select> (dropdown) no formulário da API de teste.
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=ClassificacaoOcorrencia.objects.filter(parent__isnull=True),
        source='parent',
        write_only=True,
        required=False,
        allow_null=True,
        label='Grupo Pai'
    )

    # Campos com validação de unicidade explícita
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
        fields = [
            'url',
            'id',
            'codigo',
            'nome',
            'parent',       # Campo de leitura (mostra o objeto pai)
            'parent_id',    # Campo de escrita (recebe o ID do pai)
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# Serializer para a Lixeira, mostra apenas os campos relevantes.
# -----------------------------------------------------------------------------
class ClassificacaoOcorrenciaLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="classificacaoocorrencia-detail")
    parent = ClassificacaoOcorrenciaNestedSerializer(read_only=True)

    class Meta:
        model = ClassificacaoOcorrencia
        fields = ['url', 'id', 'codigo', 'nome', 'parent', 'deleted_at']
        read_only_fields = ['deleted_at']