from rest_framework import serializers
from .models import Autoridade, Cargo
from cargos.serializers import CargoSerializer
from usuarios.serializers import UserNestedSerializer

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
        """Valida se o nome já existe (após conversão para maiúsculas)"""
        nome_upper = value.upper()
        
        # Se está editando, exclui o próprio registro da verificação
        instance_id = self.instance.id if self.instance else None
        
        # Verifica se já existe outro registro com este nome (em uppercase)
        exists = Autoridade.objects.filter(nome=nome_upper).exclude(id=instance_id).exists()
        
        if exists:
            raise serializers.ValidationError("Já existe uma autoridade com este nome.")
        
        return value

class AutoridadeLixeiraSerializer(serializers.ModelSerializer):
    cargo = CargoSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Autoridade
        fields = ['id', 'nome', 'cargo', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']