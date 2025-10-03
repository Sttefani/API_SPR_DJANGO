from rest_framework import serializers
from .models import UnidadeDemandante
from usuarios.serializers import UserNestedSerializer
import unicodedata


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
        """Valida se a sigla já existe (considerando variações com/sem acento)"""
        sigla_upper = value.upper()
        sigla_normalizada = self.remover_acentos(sigla_upper)
        
        instance_id = self.instance.id if self.instance else None
        outras = UnidadeDemandante.objects.exclude(id=instance_id)
        
        for outra in outras:
            outra_normalizada = self.remover_acentos(outra.sigla.upper())
            if outra_normalizada == sigla_normalizada:
                raise serializers.ValidationError(
                    f'Já existe uma unidade com sigla similar: "{outra.sigla}"'
                )
        
        return value
   
    def validate_nome(self, value):
        """Valida se o nome já existe (considerando variações com/sem acento)"""
        nome_upper = value.upper()
        nome_normalizado = self.remover_acentos(nome_upper)
        
        instance_id = self.instance.id if self.instance else None
        outras = UnidadeDemandante.objects.exclude(id=instance_id)
        
        for outra in outras:
            outra_normalizada = self.remover_acentos(outra.nome.upper())
            if outra_normalizada == nome_normalizado:
                raise serializers.ValidationError(
                    f'Já existe uma unidade com nome similar: "{outra.nome}"'
                )
        
        return value
    
    @staticmethod
    def remover_acentos(texto):
        """Remove acentos para comparação"""
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join([c for c in nfkd if not unicodedata.combining(c)])


class UnidadeDemandanteLixeiraSerializer(serializers.ModelSerializer):
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = UnidadeDemandante
        fields = ['id', 'sigla', 'nome', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']