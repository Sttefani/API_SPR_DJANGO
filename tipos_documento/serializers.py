# tipos_documento/serializers.py

from rest_framework import serializers
from .models import TipoDocumento
from rest_framework.validators import UniqueValidator

class TipoDocumentoSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="tipodocumento-detail")
    nome = serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(queryset=TipoDocumento.objects.all(), message="Já existe um tipo de documento com este nome.")]
    )
    class Meta:
        model = TipoDocumento
        fields = ['url', 'id', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class TipoDocumentoLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="tipodocumento-detail")
    class Meta:
        model = TipoDocumento
        fields = ['url', 'id', 'nome', 'deleted_at']
        read_only_fields = ['deleted_at']