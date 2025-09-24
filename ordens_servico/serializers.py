# ordens_servico/serializers.py

from rest_framework import serializers

from autoridades.serializers import AutoridadeSerializer
from procedimentos_cadastrados.serializers import ProcedimentoCadastradoSerializer
from tipos_documento.serializers import TipoDocumentoSerializer
from unidades_demandantes.serializers import UnidadeDemandanteSerializer
from .models import OrdemServico
from usuarios.serializers import UserNestedSerializer
from ocorrencias.serializers import OcorrenciaListSerializer # Para mostrar um resumo da ocorrência


class OrdemServicoSerializer(serializers.ModelSerializer):
    """
    Serializer para exibir os detalhes completos de uma Ordem de Serviço.
    """
    # Mostra detalhes de quem emitiu e de quem tomou ciência
    created_by = UserNestedSerializer(read_only=True)
    ciente_por = UserNestedSerializer(read_only=True)
    
    # Mostra um resumo da ocorrência pai
    ocorrencia = OcorrenciaListSerializer(read_only=True)
    
    # --- A CORREÇÃO ESTÁ AQUI ---
    # Adiciona os campos de leitura aninhada para os dados espelhados
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)
    autoridade_demandante = AutoridadeSerializer(read_only=True)
    procedimento = ProcedimentoCadastradoSerializer(read_only=True)
    tipo_documento_referencia = TipoDocumentoSerializer(read_only=True)
    
    # Campo calculado para a data de vencimento
    data_vencimento = serializers.DateTimeField(read_only=True)

    class Meta:
        model = OrdemServico
        # Mostra todos os campos do modelo
        fields = '__all__'


class CriarOrdemServicoSerializer(serializers.ModelSerializer):
    """
    Serializer para a criação de uma nova Ordem de Serviço.
    Define os campos que o gestor precisa preencher.
    """
    class Meta:
        model = OrdemServico
        # Lista apenas os campos que o usuário preenche ao criar
        fields = [
            'prazo_dias',
            'tipo_documento_referencia',
            'numero_documento_referencia',
            'processo_sei_referencia',
            'processo_judicial_referencia'
        ]

    def create(self, validated_data):
        # Pega a ocorrência e o usuário do contexto passado pela View
        ocorrencia = self.context['ocorrencia']
        user = self.context['request'].user

        # Copia os dados "espelhados" da ocorrência para a OS
        validated_data['ocorrencia'] = ocorrencia
        validated_data['unidade_demandante'] = ocorrencia.unidade_demandante
        validated_data['autoridade_demandante'] = ocorrencia.autoridade
        validated_data['procedimento'] = ocorrencia.procedimento_cadastrado
        
        # Define o usuário que criou
        validated_data['created_by'] = user
        
        # Cria a instância da Ordem de Serviço
        ordem_servico = OrdemServico.objects.create(**validated_data)
        return ordem_servico


class TomarCienciaSerializer(serializers.Serializer):
    """
    Serializer de ação para o perito "assinar" a ciência da Ordem de Serviço.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label="Senha de Confirmação",
        help_text="Confirme sua senha para registrar ciência."
    )

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        password = attrs.get('password')

        if not user.check_password(password):
            raise serializers.ValidationError({"password": "Senha incorreta. A ciência não pode ser registrada."})
        
        return attrs

