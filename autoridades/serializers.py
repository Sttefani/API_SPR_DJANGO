# autoridades/serializers.py

from rest_framework import serializers
from .models import Autoridade, Cargo
from rest_framework.validators import UniqueValidator
from cargos.serializers import CargoSerializer  # Importa o serializer de Cargo


class AutoridadeSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="autoridade-detail")

    # Para LEITURA: Mostra os detalhes do cargo usando o serializer aninhado
    cargo = CargoSerializer(read_only=True)

    # Para ESCRITA: Usa o ID do cargo para criar/atualizar a relação
    cargo_id = serializers.PrimaryKeyRelatedField(
        queryset=Cargo.objects.all(), source='cargo', write_only=True
    )

    nome = serializers.CharField(
        max_length=255,
        validators=[
            UniqueValidator(queryset=Autoridade.objects.all(), message="Já existe uma autoridade com este nome.")]
    )

    class Meta:
        model = Autoridade
        fields = ['url', 'id', 'nome', 'cargo', 'cargo_id', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class AutoridadeLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="autoridade-detail")
    cargo = CargoSerializer(read_only=True)

    class Meta:
        model = Autoridade
        fields = ['url', 'id', 'nome', 'cargo', 'deleted_at']
        read_only_fields = ['deleted_at']


