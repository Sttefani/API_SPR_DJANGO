# ocorrencias/serializers.py

from rest_framework import serializers
from django.utils import timezone
import datetime
from .models import Ocorrencia, ServicoPericial, UnidadeDemandante, Autoridade, Cidade, ClassificacaoOcorrencia, \
    ProcedimentoCadastrado, TipoDocumento, Exame
from usuarios.models import User

# Importando serializers aninhados dos outros apps
from servicos_periciais.serializers import ServicoPericialSerializer
from unidades_demandantes.serializers import UnidadeDemandanteSerializer
from autoridades.serializers import AutoridadeSerializer
from cidades.serializers import CidadeSerializer
from classificacoes.serializers import ClassificacaoOcorrenciaSerializer
from procedimentos_cadastrados.serializers import ProcedimentoCadastradoSerializer
from tipos_documento.serializers import TipoDocumentoSerializer
from exames.serializers import ExameNestedSerializer
from usuarios.serializers import UserManagementSerializer  # Para mostrar detalhes do perito/usuário


class OcorrenciaListSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer otimizado para a LISTAGEM de ocorrências, com campos de prazo calculados.
    """
    url = serializers.HyperlinkedIdentityField(view_name="ocorrencia-detail")
    status_prazo = serializers.SerializerMethodField()
    dias_prazo = serializers.SerializerMethodField()
    servico_pericial = ServicoPericialSerializer(read_only=True)
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            'url', 'id', 'numero_ocorrencia', 'status', 'servico_pericial',
            'unidade_demandante', 'data_fato', 'created_at',
            'status_prazo', 'dias_prazo'
        ]

    def get_status_prazo(self, obj):
        if obj.data_finalizacao: return 'CONCLUIDO'
        dias_corridos = (timezone.now() - obj.created_at).days
        if dias_corridos <= 10:
            return 'NO_PRAZO'
        elif dias_corridos <= 20:
            return 'PRORROGADO'
        else:
            return 'ATRASADO'

    def get_dias_prazo(self, obj):
        if obj.data_finalizacao:
            dias_totais = (obj.data_finalizacao - obj.created_at).days
            return f"Concluído em {dias_totais} dias"
        dias_corridos = (timezone.now() - obj.created_at).days
        return f"{dias_corridos} dias corridos"


class OcorrenciaDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer para a CRIAÇÃO e visualização de DETALHES de uma ocorrência.
    """
    url = serializers.HyperlinkedIdentityField(view_name="ocorrencia-detail")

    # --- Campos de Relação (Leitura com aninhamento) ---
    servico_pericial = ServicoPericialSerializer(read_only=True)
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)
    autoridade = AutoridadeSerializer(read_only=True)
    cidade = CidadeSerializer(read_only=True)
    classificacao = ClassificacaoOcorrenciaSerializer(read_only=True)
    procedimento_cadastrado = ProcedimentoCadastradoSerializer(read_only=True)
    tipo_documento_origem = TipoDocumentoSerializer(read_only=True)
    perito_atribuido = UserManagementSerializer(read_only=True)
    exames_solicitados = ExameNestedSerializer(many=True, read_only=True)
    created_by = UserManagementSerializer(read_only=True)  # Para mostrar quem registrou

    # --- Campos de Relação (Escrita com ID) ---
    servico_pericial_id = serializers.PrimaryKeyRelatedField(queryset=ServicoPericial.objects.all(),
                                                             source='servico_pericial', write_only=True,
                                                             label="Serviço Pericial")
    unidade_demandante_id = serializers.PrimaryKeyRelatedField(queryset=UnidadeDemandante.objects.all(),
                                                               source='unidade_demandante', write_only=True,
                                                               label="Unidade Demandante")
    autoridade_id = serializers.PrimaryKeyRelatedField(queryset=Autoridade.objects.all(), source='autoridade',
                                                       write_only=True, label="Autoridade")
    cidade_id = serializers.PrimaryKeyRelatedField(queryset=Cidade.objects.all(), source='cidade', write_only=True,
                                                   label="Cidade")
    classificacao_id = serializers.PrimaryKeyRelatedField(queryset=ClassificacaoOcorrencia.objects.all(),
                                                          source='classificacao', write_only=True,
                                                          label="Classificação")
    procedimento_cadastrado_id = serializers.PrimaryKeyRelatedField(queryset=ProcedimentoCadastrado.objects.all(),
                                                                    source='procedimento_cadastrado', write_only=True,
                                                                    required=False, allow_null=True,
                                                                    label="Procedimento")
    tipo_documento_origem_id = serializers.PrimaryKeyRelatedField(queryset=TipoDocumento.objects.all(),
                                                                  source='tipo_documento_origem', write_only=True,
                                                                  required=False, allow_null=True,
                                                                  label="Tipo de Documento")
    perito_atribuido_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(perfil='PERITO'),
                                                             source='perito_atribuido', write_only=True, required=False,
                                                             allow_null=True, label="Perito Atribuído")
    exames_solicitados_ids = serializers.PrimaryKeyRelatedField(queryset=Exame.objects.all(),
                                                                source='exames_solicitados', write_only=True, many=True,
                                                                required=False, label="Exames Solicitados")

    class Meta:
        model = Ocorrencia
        fields = '__all__'

    def validate(self, data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            servico_selecionado = data.get('servico_pericial')

            # Valida se o usuário pode registrar ocorrência no serviço pericial selecionado
            if not user.servicos_periciais.filter(pk=servico_selecionado.pk).exists() and not user.is_superuser:
                raise serializers.ValidationError({
                                                      "servico_pericial_id": "Você não tem permissão para registrar ocorrências neste serviço pericial."})
        return data


class OcorrenciaUpdateSerializer(OcorrenciaDetailSerializer):
    """
    Serializer para a EDIÇÃO, com campos e lógicas de validação bloqueados.
    """

    class Meta(OcorrenciaDetailSerializer.Meta):
        # Esconde campos que não devem ser editados diretamente na tela de edição principal
        read_only_fields = ('status', 'data_finalizacao')

    def validate(self, data):
        instance = self.instance
        request = self.context.get('request')
        user = request.user if request and hasattr(request, 'user') else None

        # --- Validação da Regra de 72h para o Histórico ---
        if 'historico' in data and data['historico'] != instance.historico:
            if user and user.is_superuser:
                pass  # Super Admin pode editar sempre
            else:
                # Usa a data da última edição se existir, senão, a data de criação
                data_base_prazo = instance.historico_ultima_edicao or instance.created_at
                if data_base_prazo:
                    prazo_edicao = data_base_prazo + datetime.timedelta(hours=72)
                    if timezone.now() > prazo_edicao:
                        raise serializers.ValidationError({
                            "historico": "Prazo de 72 horas para edição do histórico expirou. Apenas um Super Admin pode alterar."
                        })

        # --- Validação para campos que só o Super Admin pode alterar ---
        if user and not user.is_superuser:
            if 'data_fato' in data and data.get('data_fato') != instance.data_fato:
                raise serializers.ValidationError({"data_fato": "Apenas um Super Admin pode alterar a Data do Fato."})
            if 'hora_fato' in data and data.get('hora_fato') != instance.hora_fato:
                raise serializers.ValidationError({"hora_fato": "Apenas um Super Admin pode alterar a Hora do Fato."})

        return super().validate(data)