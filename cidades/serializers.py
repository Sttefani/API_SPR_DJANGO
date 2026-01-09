# cidades/serializers.py

from rest_framework import serializers
from .models import Cidade, Bairro
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer


# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL DE CIDADE
# -----------------------------------------------------------------------------


class CidadeSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(
        max_length=100,
        validators=[
            UniqueValidator(
                queryset=Cidade.objects.all(),
                message="Já existe uma cidade com este nome.",
            )
        ],
    )
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Cidade
        fields = [
            "id",
            "nome",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["created_at", "updated_at", "created_by", "updated_by"]


# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA DE CIDADE
# -----------------------------------------------------------------------------


class CidadeLixeiraSerializer(serializers.ModelSerializer):
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Cidade
        fields = ["id", "nome", "deleted_at", "deleted_by"]
        read_only_fields = ["deleted_at", "deleted_by"]


# -----------------------------------------------------------------------------
# SERIALIZERS DE BAIRRO
# -----------------------------------------------------------------------------


class BairroSerializer(serializers.ModelSerializer):
    """Serializer completo de Bairro para CRUD"""

    cidade_nome = serializers.CharField(source="cidade.nome", read_only=True)
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Bairro
        fields = [
            "id",
            "nome",
            "cidade",
            "cidade_nome",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["created_at", "updated_at", "created_by", "updated_by"]

    def validate(self, data):
        """Valida duplicidade de bairro na mesma cidade"""
        nome = data.get("nome", "").upper().strip()
        cidade = data.get("cidade")

        # Normaliza o nome para comparação
        nome_normalizado = " ".join(nome.split())

        # Verifica se já existe (excluindo o próprio registro em caso de update)
        queryset = Bairro.objects.filter(nome__iexact=nome_normalizado, cidade=cidade)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                {
                    "nome": f"Já existe um bairro '{nome_normalizado}' cadastrado em {cidade.nome}."
                }
            )

        return data


class BairroDropdownSerializer(serializers.ModelSerializer):
    """Serializer simplificado para dropdown"""

    class Meta:
        model = Bairro
        fields = ["id", "nome"]


class BairroLixeiraSerializer(serializers.ModelSerializer):
    """Serializer para lixeira de bairros"""

    deleted_by = UserNestedSerializer(read_only=True)
    cidade_nome = serializers.CharField(source="cidade.nome", read_only=True)

    class Meta:
        model = Bairro
        fields = ["id", "nome", "cidade_nome", "deleted_at", "deleted_by"]
        read_only_fields = ["deleted_at", "deleted_by"]
