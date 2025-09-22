# autoridades/serializers.py

from rest_framework import serializers
from .models import Autoridade, Cargo
from rest_framework.validators import UniqueValidator
from cargos.serializers import CargoSerializer # Importa o serializer de Cargo
from usuarios.serializers import UserNestedSerializer

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class AutoridadeSerializer(serializers.ModelSerializer):
    # Para LEITURA: Mostra os detalhes do cargo usando o serializer aninhado
    cargo = CargoSerializer(read_only=True)
    
    # Para ESCRITA: Usa o ID do cargo para criar/atualizar a relação
    cargo_id = serializers.PrimaryKeyRelatedField(
        queryset=Cargo.objects.all(), source='cargo', write_only=True, label='Cargo'
    )

    nome = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(queryset=Autoridade.objects.all(), message="Já existe uma autoridade com este nome.")]
    )

    class Meta:
        model = Autoridade
        # O campo 'url' foi removido
        fields = ['id', 'nome', 'cargo', 'cargo_id', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class AutoridadeLixeiraSerializer(serializers.ModelSerializer):
    cargo = CargoSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Autoridade
        # O campo 'url' foi removido
        fields = ['id', 'nome', 'cargo', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']