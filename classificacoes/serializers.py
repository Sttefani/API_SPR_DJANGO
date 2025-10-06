from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer
from servicos_periciais.models import ServicoPericial # <-- ADICIONADO
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

    # --- INÍCIO DA MODIFICAÇÃO ---
    # Campo para exibir os serviços já associados (apenas leitura)
    servicos_periciais = serializers.SerializerMethodField()

    # Campo para receber a lista de IDs dos serviços ao salvar (apenas escrita)
    servicos_periciais_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False # Permite não enviar a lista ou enviar uma lista vazia
    )
    # --- FIM DA MODIFICAÇÃO ---

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
            'servicos_periciais', # <-- ADICIONADO
            'servicos_periciais_ids', # <-- ADICIONADO
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

    # --- INÍCIO DAS NOVAS FUNÇÕES ---
    def get_servicos_periciais(self, obj):
        # Retorna uma lista de dicionários simples para o frontend consumir facilmente
        return obj.servicos_periciais.values('id', 'sigla', 'nome')

    def create(self, validated_data):
        # Remove a lista de IDs antes de chamar o 'create' do pai
        servicos_ids = validated_data.pop('servicos_periciais_ids', [])
        classificacao = super().create(validated_data)
        # Se a lista de IDs foi enviada, estabelece a relação ManyToMany
        if servicos_ids:
            classificacao.servicos_periciais.set(servicos_ids)
        return classificacao

    def update(self, instance, validated_data):
        # Remove a lista de IDs antes de chamar o 'update' do pai
        servicos_ids = validated_data.pop('servicos_periciais_ids', None)
        classificacao = super().update(instance, validated_data)
        # Se a lista de IDs foi enviada (mesmo que vazia), atualiza a relação
        if servicos_ids is not None:
            classificacao.servicos_periciais.set(servicos_ids)
        return classificacao
    # --- FIM DAS NOVAS FUNÇÕES ---

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