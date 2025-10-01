from rest_framework import serializers
from .models import UnidadeDemandante
from usuarios.serializers import UserNestedSerializer

class UnidadeDemandanteSerializer(serializers.ModelSerializer):
    sigla = serializers.CharField(max_length=20)
    nome = serializers.CharField(max_length=255)
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = UnidadeDemandante
        fields = ['id', 'sigla', 'nome', 'created_at', 'updated_at', 'created_by', 'updated_by']
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def validate_sigla(self, value):
        """Valida se a sigla já existe (após conversão para maiúsculas)"""
        sigla_upper = value.upper()
        instance_id = self.instance.id if self.instance else None
        exists = UnidadeDemandante.objects.filter(sigla=sigla_upper).exclude(id=instance_id).exists()
        if exists:
            raise serializers.ValidationError("Já existe uma unidade com esta sigla.")
        return value
    
    def validate_nome(self, value):
        """Valida se o nome já existe (após conversão para maiúsculas)"""
        nome_upper = value.upper()
        instance_id = self.instance.id if self.instance else None
        exists = UnidadeDemandante.objects.filter(nome=nome_upper).exclude(id=instance_id).exists()
        if exists:
            raise serializers.ValidationError("Já existe uma unidade com este nome.")
        return value

class UnidadeDemandanteLixeiraSerializer(serializers.ModelSerializer):
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = UnidadeDemandante
        fields = ['id', 'sigla', 'nome', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']