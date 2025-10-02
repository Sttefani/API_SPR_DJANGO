from rest_framework import serializers
from django.db import IntegrityError
from .models import ProcedimentoCadastrado, Procedimento
from procedimentos.serializers import ProcedimentoSerializer
from usuarios.serializers import UserNestedSerializer

class ProcedimentoCadastradoSerializer(serializers.ModelSerializer):
    tipo_procedimento = ProcedimentoSerializer(read_only=True)
    tipo_procedimento_id = serializers.PrimaryKeyRelatedField(
        queryset=Procedimento.objects.all(), 
        source='tipo_procedimento', 
        write_only=True, 
        label='Tipo de Procedimento'
    )
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)
    numero_completo = serializers.SerializerMethodField()

    class Meta:
        model = ProcedimentoCadastrado
        fields = [
            'id', 'tipo_procedimento', 'tipo_procedimento_id', 'numero', 'ano',
            'numero_completo', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
        validators = []  # IMPORTANTE: Remove validators automáticos do DRF
    
    def get_numero_completo(self, obj):
        return f"{obj.tipo_procedimento.sigla} - {obj.numero}/{obj.ano}"
    
    def validate_numero(self, value):
        """Converte número para maiúsculas"""
        return value.upper()
    
    def validate(self, data):
        """Validação manual antes de salvar"""
        tipo_procedimento = data.get('tipo_procedimento')
        numero = data.get('numero')
        ano = data.get('ano')
        
        # Se está editando, exclui o próprio registro
        instance_id = self.instance.id if self.instance else None
        
        exists = ProcedimentoCadastrado.objects.filter(
            tipo_procedimento=tipo_procedimento,
            numero=numero,
            ano=ano
        ).exclude(id=instance_id).exists()
        
        if exists:
            raise serializers.ValidationError({
                'numero': f'Já existe um procedimento {tipo_procedimento.sigla} nº {numero}/{ano} cadastrado no sistema.'
            })
        
        return data

class ProcedimentoCadastradoLixeiraSerializer(serializers.ModelSerializer):
    tipo_procedimento = ProcedimentoSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)
    numero_completo = serializers.SerializerMethodField()

    class Meta:
        model = ProcedimentoCadastrado
        fields = ['id', 'tipo_procedimento', 'numero', 'ano', 'numero_completo', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']
    
    def get_numero_completo(self, obj):
        return f"{obj.tipo_procedimento.sigla} - {obj.numero}/{obj.ano}"