# cidades/serializers.py

from rest_framework import serializers
from .models import Cidade
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer 


# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------


class CidadeSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(
        max_length=100,
        validators=[
            UniqueValidator(
                queryset=Cidade.objects.all(),
                message="Já existe uma cidade com este nome."
            )
        ]
    )

    class Meta:
        model = Cidade
        # O campo 'url' foi removido
        fields = ['id', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (COM 'deleted_by' CORRIGIDO)
# -----------------------------------------------------------------------------


class CidadeLixeiraSerializer(serializers.ModelSerializer):
    # Mostra os detalhes do usuário que deletou, em vez de um ID
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Cidade
        # O campo 'url' foi removido
        fields = ['id', 'nome', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']