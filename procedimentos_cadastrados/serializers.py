from rest_framework import serializers
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
    
    # Campo computado para exibição na listagem
    numero_completo = serializers.SerializerMethodField()

    class Meta:
        model = ProcedimentoCadastrado
        fields = [
            'id', 'tipo_procedimento', 'tipo_procedimento_id', 'numero', 'ano',
            'numero_completo', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=ProcedimentoCadastrado.objects.all(),
                fields=['tipo_procedimento', 'numero', 'ano'],
                message="Este número de procedimento já está cadastrado para este tipo e ano."
            )
        ]
    
    def get_numero_completo(self, obj):
        """Retorna formato: APF - 123/2025"""
        return f"{obj.tipo_procedimento.sigla} - {obj.numero}/{obj.ano}"

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