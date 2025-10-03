from rest_framework import serializers
from .models import Autoridade, Cargo
from cargos.serializers import CargoSerializer
from usuarios.serializers import UserNestedSerializer
import unicodedata
from rest_framework import serializers


class AutoridadeSerializer(serializers.ModelSerializer):
    cargo = CargoSerializer(read_only=True)
    cargo_id = serializers.PrimaryKeyRelatedField(
        queryset=Cargo.objects.all(), 
        source='cargo', 
        write_only=True, 
        label='Cargo'
    )
    nome = serializers.CharField(max_length=255)
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Autoridade
        fields = ['id', 'nome', 'cargo', 'cargo_id', 'created_at', 'updated_at', 'created_by', 'updated_by']
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
  
def validate_nome(self, value):
    """Valida se o nome já existe (considerando variações com/sem acento)"""
    nome_upper = value.upper()
    nome_normalizado = self.remover_acentos(nome_upper)
    
    # Se está editando, exclui o próprio registro da verificação
    instance_id = self.instance.id if self.instance else None
    
    # Busca outras autoridades (exceto a atual)
    outras = Autoridade.objects.exclude(id=instance_id)
    
    # Verifica se existe nome similar (sem considerar acentos)
    for outra in outras:
        outra_normalizada = self.remover_acentos(outra.nome.upper())
        if outra_normalizada == nome_normalizado:
            raise serializers.ValidationError(
                f'Já existe uma autoridade com nome similar: "{outra.nome}"'
            )
    
    return value

@staticmethod
def remover_acentos(texto):
    """Remove acentos para comparação"""
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)])

class AutoridadeLixeiraSerializer(serializers.ModelSerializer):
    cargo = CargoSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Autoridade
        fields = ['id', 'nome', 'cargo', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']