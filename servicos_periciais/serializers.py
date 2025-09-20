# servicos_periciais/serializers.py

from rest_framework import serializers
from .models import ServicoPericial
import rest_framework.validators
from rest_framework.validators import UniqueValidator # <-- IMPORTE AQUI


class ServicoPericialSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="servico-pericial-detail")

    sigla = serializers.CharField(
        max_length=10,
        validators=[
            UniqueValidator(queryset=ServicoPericial.objects.all(), message="Já existe um serviço com esta sigla.")]
    )
    nome = serializers.CharField(
        max_length=50,
        validators=[
            UniqueValidator(queryset=ServicoPericial.objects.all(), message="Já existe um serviço com este nome.")]
    )

    class Meta:
        model = ServicoPericial
        fields = ['url', 'id', 'sigla', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# ADICIONE ESTE NOVO SERIALIZER
class ServicoPericialLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="servico-pericial-detail")
    class Meta:
        model = ServicoPericial
        fields = ['url', 'id', 'sigla', 'nome', 'deleted_at'] # <-- O campo relevante aqui!
        read_only_fields = ['deleted_at']


class ServicoPericialNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicoPericial
        fields = ['id', 'sigla', 'nome']