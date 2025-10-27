# ordens_servico/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model

from autoridades.serializers import AutoridadeSerializer
from procedimentos_cadastrados.serializers import ProcedimentoCadastradoSerializer
from tipos_documento.models import TipoDocumento
from tipos_documento.serializers import TipoDocumentoSerializer
from unidades_demandantes.serializers import UnidadeDemandanteSerializer
from .models import OrdemServico
from usuarios.serializers import UserNestedSerializer
from ocorrencias.serializers import OcorrenciaListSerializer

User = get_user_model()


# =============================================================================
# SERIALIZER PRINCIPAL (LISTAGEM E DETALHES)
# =============================================================================
class OrdemServicoSerializer(serializers.ModelSerializer):
    """
    Serializer completo para visualização de OS.
    Inclui dados calculados e relacionamentos aninhados.
    """

    # Relações aninhadas (read-only)
    ocorrencia = OcorrenciaListSerializer(read_only=True)
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)
    ordenada_por = UserNestedSerializer(read_only=True)
    ciente_por = UserNestedSerializer(read_only=True)
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)
    autoridade_demandante = AutoridadeSerializer(read_only=True)
    procedimento = ProcedimentoCadastradoSerializer(read_only=True)
    tipo_documento_referencia = TipoDocumentoSerializer(read_only=True)

    # Campos calculados
    data_vencimento = serializers.SerializerMethodField()
    dias_desde_emissao = serializers.SerializerMethodField()
    dias_restantes = serializers.SerializerMethodField()
    esta_vencida = serializers.SerializerMethodField()
    urgencia = serializers.SerializerMethodField()
    percentual_prazo_consumido = serializers.SerializerMethodField()
    prazo_acumulado_total = serializers.SerializerMethodField()
    acao_necessaria = serializers.SerializerMethodField()
    reiteracoes = serializers.SerializerMethodField()
    perito_destinatario = serializers.SerializerMethodField()

    class Meta:
        model = OrdemServico
        fields = [
            "id",
            "numero_os",
            "prazo_dias",
            "status",
            "data_conclusao",
            "data_prazo",  # ✅ CAMPO NOVO ADICIONADO
            "texto_padrao",
            "observacoes_administrativo",
            "justificativa_atraso",
            "numero_documento_referencia",
            "processo_sei_referencia",
            "processo_judicial_referencia",
            "data_primeira_visualizacao",
            "data_ciencia",
            "ip_ciencia",
            "created_at",
            "updated_at",
            "numero_reiteracao",
            # Relações
            "ocorrencia",
            "created_by",
            "updated_by",
            "ordenada_por",
            "ciente_por",
            "unidade_demandante",
            "autoridade_demandante",
            "procedimento",
            "tipo_documento_referencia",
            "os_original",
            # Campos calculados
            "data_vencimento",
            "dias_desde_emissao",
            "dias_restantes",
            "esta_vencida",
            "urgencia",
            "percentual_prazo_consumido",
            "prazo_acumulado_total",
            "acao_necessaria",
            "reiteracoes",
            "perito_destinatario",
            "concluida_com_atraso",  #
        ]

    def get_data_vencimento(self, obj):
        return obj.data_vencimento

    def get_dias_desde_emissao(self, obj):
        return obj.dias_desde_emissao

    def get_dias_restantes(self, obj):
        return obj.dias_restantes

    def get_esta_vencida(self, obj):
        return obj.esta_vencida

    def get_urgencia(self, obj):
        return obj.urgencia

    def get_percentual_prazo_consumido(self, obj):
        return obj.percentual_prazo_consumido

    def get_prazo_acumulado_total(self, obj):
        return obj.prazo_acumulado_total

    def get_perito_destinatario(self, obj):
        """Retorna o perito que deve cumprir esta OS"""
        if obj.ocorrencia and obj.ocorrencia.perito_atribuido:
            perito = obj.ocorrencia.perito_atribuido
            return {
                "id": perito.id,
                "nome_completo": perito.nome_completo,
                "email": perito.email,
            }
        return None

    def get_acao_necessaria(self, obj):
        """
        Indica qual ação o usuário logado precisa tomar nesta OS.
        """
        request = self.context.get("request")
        if not request:
            return None

        user = request.user
        perito_destinatario = obj.ocorrencia.perito_atribuido

        # Se o perito ainda não deu ciência
        if (
            not obj.ciente_por
            and perito_destinatario
            and user.id == perito_destinatario.id
        ):
            return "TOMAR_CIENCIA"

        # Se está aberta mas não iniciou o trabalho
        if (
            obj.status == OrdemServico.Status.ABERTA
            and perito_destinatario
            and user.id == perito_destinatario.id
        ):
            return "INICIAR_TRABALHO"

        # Se está vencida e sem justificativa
        if (
            obj.esta_vencida
            and not obj.justificativa_atraso
            and perito_destinatario
            and user.id == perito_destinatario.id
        ):
            return "JUSTIFICAR_ATRASO"

        # Se o admin precisa reiterar (vencida há mais de 3 dias)
        if (
            obj.esta_vencida
            and obj.dias_restantes
            and obj.dias_restantes < -3
            and user.perfil in ["ADMINISTRATIVO", "SUPER_ADMIN"]
        ):
            return "REITERAR"

        return None

    def get_reiteracoes(self, obj):
        """Retorna as reiterações desta OS (se for a original)"""
        if obj.numero_reiteracao == 0:  # É a original
            reiteracoes = obj.reiteracoes.filter(deleted_at__isnull=True).order_by(
                "numero_reiteracao"
            )
            return [
                {
                    "id": r.id,
                    "numero_os": r.numero_os,
                    "numero_reiteracao": r.numero_reiteracao,
                    "prazo_dias": r.prazo_dias,
                    "status": r.status,
                    "created_at": r.created_at,
                }
                for r in reiteracoes
            ]
        return []

    def to_representation(self, instance):
        """
        Customiza o que é exibido no JSON baseado no perfil do usuário.
        PERITO só vê detalhes completos APÓS dar ciência.
        """
        ret = super().to_representation(instance)
        request = self.context.get("request")
        if not request:
            return ret

        user = request.user
        perito_destinatario = instance.ocorrencia.perito_atribuido

        # Se o perito ainda não deu ciência, esconde alguns detalhes
        if (
            not instance.ciente_por
            and perito_destinatario
            and user.id == perito_destinatario.id
            and user.perfil not in ["ADMINISTRATIVO", "SUPER_ADMIN"]
        ):

            # Campos que ficam ocultos até dar ciência
            campos_ocultos = [
                "texto_padrao",
                "numero_documento_referencia",
                "processo_sei_referencia",
                "processo_judicial_referencia",
                "observacoes_administrativo",
            ]

            for campo in campos_ocultos:
                ret.pop(campo, None)

            ret["detalhes_ocultos"] = True
            ret["mensagem"] = (
                "Dê ciência nesta OS para visualizar os detalhes completos."
            )
        else:
            ret["detalhes_ocultos"] = False

        return ret


# =============================================================================
# SERIALIZER PARA CRIAR OS (COM ASSINATURA DIGITAL)
# =============================================================================
class CriarOrdemServicoComAssinaturaSerializer(serializers.Serializer):
    """
    Serializer para criar OS com assinatura digital do administrativo.
    """

    # Dados da OS
    prazo_dias = serializers.IntegerField(
        min_value=1,
        max_value=365,
        label="Prazo (dias)",
        help_text="Prazo em dias para conclusão da OS",
    )

    ordenada_por_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(status="ATIVO"),
        label="Ordenada por",
        help_text="Diretor ou responsável que ordenou a emissão desta OS",
    )

    observacoes_administrativo = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
        label="Observações",
        help_text="Observações adicionais sobre esta OS",
    )

    tipo_documento_referencia_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoDocumento.objects.all(),
        required=False,
        allow_null=True,
        label="Tipo de Documento",
    )

    numero_documento_referencia = serializers.CharField(
        max_length=50, required=False, allow_blank=True, label="Nº Documento"
    )

    processo_sei_referencia = serializers.CharField(
        max_length=50, required=False, allow_blank=True, label="Processo SEI"
    )

    processo_judicial_referencia = serializers.CharField(
        max_length=50, required=False, allow_blank=True, label="Processo Judicial"
    )

    # Assinatura digital
    email = serializers.EmailField(
        write_only=True,
        label="Email (confirmação)",
        help_text="Confirme seu email para assinar digitalmente",
    )

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        label="Senha (confirmação)",
        help_text="Confirme sua senha para assinar digitalmente",
    )

    def validate(self, attrs):
        """Valida email e senha do administrativo"""
        request = self.context.get("request")
        user = request.user

        # Valida email
        if attrs.get("email") != user.email:
            raise serializers.ValidationError(
                {"email": "Email não corresponde ao usuário logado."}
            )

        # Valida senha
        if not user.check_password(attrs.get("password")):
            raise serializers.ValidationError({"password": "Senha incorreta."})

        return attrs

    def create(self, validated_data):
        """Cria a OS com os dados espelhados da ocorrência"""
        ocorrencia = self.context["ocorrencia"]
        user = self.context["request"].user

        # Remove dados da assinatura (não vão pro model)
        validated_data.pop("email")
        validated_data.pop("password")

        # Mapeia os IDs para as instâncias
        ordenada_por = validated_data.pop("ordenada_por_id")
        tipo_doc = validated_data.pop("tipo_documento_referencia_id", None)

        # Cria a OS
        ordem_servico = OrdemServico.objects.create(
            ocorrencia=ocorrencia,
            prazo_dias=validated_data["prazo_dias"],
            ordenada_por=ordenada_por,
            observacoes_administrativo=validated_data.get(
                "observacoes_administrativo", ""
            ),
            tipo_documento_referencia=tipo_doc,
            numero_documento_referencia=validated_data.get(
                "numero_documento_referencia", ""
            ),
            processo_sei_referencia=validated_data.get("processo_sei_referencia", ""),
            processo_judicial_referencia=validated_data.get(
                "processo_judicial_referencia", ""
            ),
            # Espelha dados da ocorrência
            unidade_demandante=ocorrencia.unidade_demandante,
            autoridade_demandante=ocorrencia.autoridade,
            procedimento=ocorrencia.procedimento_cadastrado,
            # Auditoria
            created_by=user,
        )

        return ordem_servico


# =============================================================================
# SERIALIZER PARA TOMAR CIÊNCIA
# =============================================================================
class TomarCienciaSerializer(serializers.Serializer):
    """
    Serializer para o perito assinar digitalmente que tomou ciência da OS.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        label="Senha de Confirmação",
        help_text="Confirme sua senha para registrar ciência digital",
    )

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user
        password = attrs.get("password")

        if not user.check_password(password):
            raise serializers.ValidationError(
                {"password": "Senha incorreta. A ciência não pode ser registrada."}
            )

        return attrs


# =============================================================================
# SERIALIZER PARA REITERAR OS
# =============================================================================
class ReiterarOrdemServicoSerializer(serializers.Serializer):
    """
    Serializer para criar uma reiteração de OS existente.
    """

    prazo_dias = serializers.IntegerField(
        min_value=1,
        max_value=30,
        label="Prazo adicional (dias)",
        help_text="Prazo da reiteração (geralmente menor: 5, 2, 1 dias)",
    )

    ordenada_por_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(status="ATIVO"),
        required=False,
        allow_null=True,
        label="Ordenada por",
        help_text="Se não informado, usa o mesmo da OS original",
    )

    observacoes_administrativo = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
        label="Observações da Reiteração",
    )

    # Assinatura digital
    email = serializers.EmailField(write_only=True, label="Email (confirmação)")

    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}, label="Senha (confirmação)"
    )

    def validate(self, attrs):
        """Valida assinatura"""
        request = self.context.get("request")
        user = request.user

        if attrs.get("email") != user.email:
            raise serializers.ValidationError(
                {"email": "Email não corresponde ao usuário logado."}
            )

        if not user.check_password(attrs.get("password")):
            raise serializers.ValidationError({"password": "Senha incorreta."})

        return attrs


# =============================================================================
# SERIALIZER PARA JUSTIFICAR ATRASO
# =============================================================================
class JustificarAtrasoSerializer(serializers.Serializer):
    """
    Serializer para o perito justificar atraso na entrega.
    """

    justificativa = serializers.CharField(
        required=True,
        max_length=2000,
        label="Justificativa",
        help_text="Explique o motivo do atraso na entrega do laudo",
    )


# =============================================================================
# SERIALIZER PARA LIXEIRA
# =============================================================================
class OrdemServicoLixeiraSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para visualização da lixeira.
    """

    ocorrencia = OcorrenciaListSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = OrdemServico
        fields = [
            "id",
            "numero_os",
            "prazo_dias",
            "status",
            "ocorrencia",
            "deleted_at",
            "deleted_by",
        ]
