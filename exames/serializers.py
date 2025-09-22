# exames/serializers.py

from rest_framework import serializers
from .models import Exame, ServicoPericial
from rest_framework.validators import UniqueValidator
from servicos_periciais.serializers import ServicoPericialSerializer
from usuarios.serializers import UserNestedSerializer # Importa para o 'deleted_by'

# -----------------------------------------------------------------------------
# SERIALIZER ANINHADO (JÁ ESTAVA CORRETO)
# -----------------------------------------------------------------------------
class ExameNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exame
        fields = ['id', 'codigo', 'nome']

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ExameSerializer(serializers.ModelSerializer):
    servico_pericial = ServicoPericialSerializer(read_only=True)
    servico_pericial_id = serializers.PrimaryKeyRelatedField(
        queryset=ServicoPericial.objects.all(), source='servico_pericial', write_only=True, label='Serviço Pericial'
    )
    parent = ExameNestedSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Exame.objects.filter(parent__isnull=True),
        source='parent', write_only=True, required=False, allow_null=True, label='Exame Pai (Grupo)'
    )
    codigo = serializers.CharField(max_length=20, validators=[
        UniqueValidator(queryset=Exame.objects.all(), message="Já existe um exame com este código.")])
    nome = serializers.CharField(max_length=255, validators=[
        UniqueValidator(queryset=Exame.objects.all(), message="Já existe um exame com este nome.")])

    class Meta:
        model = Exame
        # O campo 'url' foi removido
        fields = [
            'id', 'codigo', 'nome',
            'servico_pericial', 'servico_pericial_id',
            'parent', 'parent_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ExameLixeiraSerializer(serializers.ModelSerializer):
    servico_pericial = ServicoPericialSerializer(read_only=True)
    parent = ExameNestedSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Exame
        # O campo 'url' foi removido
        fields = ['id', 'codigo', 'nome', 'servico_pericial', 'parent', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']