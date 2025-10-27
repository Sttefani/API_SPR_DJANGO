# cargos/serializers.py
from rest_framework import serializers
from .models import Cargo
from rest_framework.validators import UniqueValidator
from usuarios.serializers import UserNestedSerializer


class CargoSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(
        max_length=100,
        validators=[
            UniqueValidator(
                queryset=Cargo.objects.all(),
                message="Já existe um cargo com este nome.",
            )
        ],
    )
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Cargo
        fields = ["id", "nome", "created_at", "updated_at", "created_by", "updated_by"]
        read_only_fields = ["created_at", "updated_at", "created_by", "updated_by"]


class CargoLixeiraSerializer(serializers.ModelSerializer):
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Cargo
        fields = ["id", "nome", "deleted_at", "deleted_by"]
        read_only_fields = ["deleted_at", "deleted_by"]
