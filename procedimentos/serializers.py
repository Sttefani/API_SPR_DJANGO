# procedimentos/serializers.py

from rest_framework import serializers
from .models import Procedimento
from rest_framework.validators import UniqueValidator

class ProcedimentoSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="procedimento-detail")
    sigla = serializers.CharField(
        max_length=20,
        validators=[UniqueValidator(queryset=Procedimento.objects.all(), message="Já existe um procedimento com esta sigla.")]
    )
    nome = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(queryset=Procedimento.objects.all(), message="Já existe um procedimento com este nome.")]
    )

    class Meta:
        model = Procedimento
        fields = ['url', 'id', 'sigla', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class ProcedimentoLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="procedimento-detail")
    class Meta:
        model = Procedimento
        fields = ['url', 'id', 'sigla', 'nome', 'deleted_at']
        read_only_fields = ['deleted_at']