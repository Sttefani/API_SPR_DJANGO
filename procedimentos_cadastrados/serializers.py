# procedimentos_cadastrados/serializers.py

from rest_framework import serializers
from .models import ProcedimentoCadastrado, Procedimento
from procedimentos.serializers import ProcedimentoSerializer


class ProcedimentoCadastradoSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="procedimentocadastrado-detail")

    # Para LEITURA: Mostra os detalhes do tipo de procedimento
    tipo_procedimento = ProcedimentoSerializer(read_only=True)

    # Para ESCRITA: Usa o ID do tipo para criar/atualizar
    tipo_procedimento_id = serializers.PrimaryKeyRelatedField(
        queryset=Procedimento.objects.all(), source='tipo_procedimento', write_only=True, label='Tipo de Procedimento'
    )

    # O campo 'ano' agora é simples, sem 'default'. A View vai cuidar disso.

    class Meta:
        model = ProcedimentoCadastrado
        fields = [
            'url', 'id', 'tipo_procedimento', 'numero', 'ano',
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


class ProcedimentoCadastradoLixeiraSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="procedimentocastrado-detail")
    tipo_procedimento = ProcedimentoSerializer(read_only=True)

    class Meta:
        model = ProcedimentoCadastrado
        fields = ['url', 'id', 'tipo_procedimento', 'numero', 'ano', 'deleted_at']
        read_only_fields = ['deleted_at']