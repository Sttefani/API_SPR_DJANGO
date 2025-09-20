# cidades/serializers.py

from rest_framework import serializers
from .models import Cidade
from rest_framework.validators import UniqueValidator  # <-- Garanta que este import está aqui


class CidadeSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="cidade-detail")

    # AQUI ESTÁ A ADIÇÃO DO VALIDADOR EXPLÍCITO
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
        fields = ['url', 'id', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class CidadeLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="cidade-detail")

    class Meta:
        model = Cidade
        fields = ['url', 'id', 'nome', 'deleted_at']
        read_only_fields = ['deleted_at']