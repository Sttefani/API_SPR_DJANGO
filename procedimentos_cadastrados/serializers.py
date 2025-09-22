# procedimentos_cadastrados/serializers.py

from rest_framework import serializers
from .models import ProcedimentoCadastrado, Procedimento
from procedimentos.serializers import ProcedimentoSerializer
from usuarios.serializers import UserNestedSerializer # Importa para o 'deleted_by'

# -----------------------------------------------------------------------------
# SERIALIZER PRINCIPAL (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ProcedimentoCadastradoSerializer(serializers.ModelSerializer):
    tipo_procedimento = ProcedimentoSerializer(read_only=True)
    tipo_procedimento_id = serializers.PrimaryKeyRelatedField(
        queryset=Procedimento.objects.all(), source='tipo_procedimento', write_only=True, label='Tipo de Procedimento'
    )

    class Meta:
        model = ProcedimentoCadastrado
        # O campo 'url' foi removido
        fields = [
            'id', 'tipo_procedimento', 'numero', 'ano',
            'tipo_procedimento_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=ProcedimentoCadastrado.objects.all(),
                fields=['tipo_procedimento', 'numero', 'ano'],
                message="Este número de procedimento já está cadastrado para este tipo e ano."
            )
        ]

# -----------------------------------------------------------------------------
# SERIALIZER DA LIXEIRA (AGORA USANDO ModelSerializer)
# -----------------------------------------------------------------------------
class ProcedimentoCadastradoLixeiraSerializer(serializers.ModelSerializer):
    tipo_procedimento = ProcedimentoSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = ProcedimentoCadastrado
        # O campo 'url' foi removido
        fields = ['id', 'tipo_procedimento', 'numero', 'ano', 'deleted_at', 'deleted_by']
        read_only_fields = ['deleted_at', 'deleted_by']

