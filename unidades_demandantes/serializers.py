# unidades_demandantes/serializers.py

from rest_framework import serializers
from .models import UnidadeDemandante
from rest_framework.validators import UniqueValidator

class UnidadeDemandanteSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="unidade-demandante-detail")
    sigla = serializers.CharField(
        max_length=20,
        validators=[UniqueValidator(queryset=UnidadeDemandante.objects.all(), message="Já existe uma unidade com esta sigla.")]
    )
    nome = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(queryset=UnidadeDemandante.objects.all(), message="Já existe uma unidade com este nome.")]
    )

    class Meta:
        model = UnidadeDemandante
        fields = ['url', 'id', 'sigla', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class UnidadeDemandanteLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="unidade-demandante-detail")
    class Meta:
        model = UnidadeDemandante
        fields = ['url', 'id', 'sigla', 'nome', 'deleted_at']
        read_only_fields = ['deleted_at']