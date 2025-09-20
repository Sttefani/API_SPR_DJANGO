from rest_framework import serializers
from .models import Cargo
from rest_framework.validators import UniqueValidator

class CargoSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="cargo-detail")
    nome = serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(queryset=Cargo.objects.all(), message="Já existe um cargo com este nome.")]
    )
    class Meta:
        model = Cargo
        fields = ['url', 'id', 'nome', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class CargoLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="cargo-detail")
    class Meta:
        model = Cargo
        fields = ['url', 'id', 'nome', 'deleted_at']
        read_only_fields = ['deleted_at']