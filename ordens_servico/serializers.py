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
    # --- Relações aninhadas para exibir nomes em vez de IDs (Leitura) ---
    ocorrencia = OcorrenciaListSerializer(read_only=True)
    created_by = UserNestedSerializer(read_only=True)
    ciente_por = UserNestedSerializer(read_only=True)
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)
    autoridade_demandante = AutoridadeSerializer(read_only=True)
    procedimento = ProcedimentoCadastradoSerializer(read_only=True)
    tipo_documento_referencia = TipoDocumentoSerializer(read_only=True)

    # --- Campo calculado ---
    data_vencimento = serializers.DateTimeField(read_only=True)

    class Meta:
        model = OrdemServico
        # AQUI ESTÁ A CORREÇÃO:
        # Lista explícita de campos para garantir que os aninhados sejam usados.
        fields = [
            'id',
            'numero_os',
            'prazo_dias',
            'status',
            'data_conclusao',
            'texto_padrao',
            'numero_documento_referencia',
            'processo_sei_referencia',
            'processo_judicial_referencia',
            'data_ciencia',
            'ip_ciencia',
            'data_vencimento',
            'created_at',
            'updated_at',
            # Campos de Relação (objetos aninhados)
            'ocorrencia',
            'created_by',
            'ciente_por',
            'unidade_demandante',
            'autoridade_demandante',
            'procedimento',
            'tipo_documento_referencia'
        ]
    # O MÉTODO QUE ESTÁ FALTANDO
    def get_acao_necessaria(self, obj):
        request = self.context.get('request')
        user = request.user
        if not obj.ciente_por and obj.ocorrencia.perito_atribuido and user.id == obj.ocorrencia.perito_atribuido.id:
            return "TOMAR_CIENCIA"
        return None

    def to_representation(self, instance):
        """
        Customiza o que é exibido no JSON.
        """
        ret = super().to_representation(instance)
        request = self.context.get('request')
        user = request.user

        # A REGRA DE NEGÓCIO PARA ESCONDER OS DETALHES
        if (not instance.ciente_por and 
            instance.ocorrencia.perito_atribuido and 
            user.id == instance.ocorrencia.perito_atribuido.id and
            user.perfil not in ['ADMINISTRATIVO', 'SUPER_ADMIN']):
            
            campos_para_esconder = ['texto_padrao', 'numero_documento_referencia', 'processo_sei_referencia', 'processo_judicial_referencia']
            for campo in campos_para_esconder:
                ret.pop(campo, None)
            
            ret['detalhes_ocultos'] = "Os detalhes completos desta OS estarão visíveis após você registrar ciência."

        return ret


class CriarOrdemServicoSerializer(serializers.ModelSerializer):
    """
    Serializer para a criação de uma nova Ordem de Serviço.
    """
    class Meta:
        model = OrdemServico
        # Apenas os campos que o usuário preenche
        fields = [
            'prazo_dias',
            'tipo_documento_referencia',
            'numero_documento_referencia',
            'processo_sei_referencia',
            'processo_judicial_referencia'
        ]

    def create(self, validated_data):
        ocorrencia = self.context['ocorrencia']
        user = self.context['request'].user

        # Copia os dados espelhados da ocorrência
        validated_data['ocorrencia'] = ocorrencia
        validated_data['unidade_demandante'] = ocorrencia.unidade_demandante
        validated_data['autoridade_demandante'] = ocorrencia.autoridade
        validated_data['procedimento'] = ocorrencia.procedimento_cadastrado
        validated_data['created_by'] = user
        
        return OrdemServico.objects.create(**validated_data)


# =============================================================================
# SERIALIZER DE AÇÃO (PARA ASSINATURA)
# =============================================================================
class TomarCienciaSerializer(serializers.Serializer):
    """
    Serializer para o perito "assinar" a ciência da OS.
    """
    password = serializers.CharField(
        write_only=True, required=True, style={'input_type': 'password'},
        label="Senha de Confirmação"
    )

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs.get('password')):
            raise serializers.ValidationError({"password": "Senha incorreta."})
        return attrs
    
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

