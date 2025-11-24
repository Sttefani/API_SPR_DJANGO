# ocorrencias/serializers.py

from rest_framework import serializers
from django.utils import timezone
import datetime

from ocorrencias.endereco_models import EnderecoOcorrencia
from usuarios.models import User
from .models import (
    Ocorrencia,
    ServicoPericial,
    UnidadeDemandante,
    Autoridade,
    Cidade,
    ClassificacaoOcorrencia,
    ProcedimentoCadastrado,
    TipoDocumento,
)
from servicos_periciais.serializers import ServicoPericialSerializer
from unidades_demandantes.serializers import UnidadeDemandanteSerializer
from autoridades.serializers import AutoridadeSerializer
from cidades.serializers import CidadeSerializer
from classificacoes.serializers import ClassificacaoOcorrenciaSerializer
from procedimentos_cadastrados.serializers import (
    ProcedimentoCadastradoSerializer,
)
from tipos_documento.serializers import TipoDocumentoSerializer
from exames.serializers import ExameNestedSerializer
from usuarios.serializers import UserNestedSerializer


# ========================================
# SERIALIZER DE ENDEREÇO
# ========================================


class EnderecoOcorrenciaSerializer(serializers.ModelSerializer):
    """Serializer para endereço de ocorrências externas"""

    endereco_completo = serializers.ReadOnlyField()
    tem_coordenadas = serializers.ReadOnlyField()

    class Meta:
        model = EnderecoOcorrencia
        fields = [
            "id",
            "ocorrencia",
            "tipo",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cep",
            "latitude",
            "longitude",
            "ponto_referencia",
            "endereco_completo",
            "tem_coordenadas",
            "created_at",
            "updated_at",
            "endereco_completo",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OcorrenciaListSerializer(serializers.ModelSerializer):
    # ... (código sem alteração)
    status_prazo = serializers.SerializerMethodField()
    dias_prazo = serializers.SerializerMethodField()
    servico_pericial = ServicoPericialSerializer(read_only=True)
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)
    perito_atribuido = UserNestedSerializer(read_only=True)
    created_by = UserNestedSerializer(read_only=True)
    esta_finalizada = serializers.BooleanField(read_only=True)
    classificacao = ClassificacaoOcorrenciaSerializer(read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "numero_ocorrencia",
            "status",
            "servico_pericial",
            "unidade_demandante",
            "data_fato",
            "created_at",
            "status_prazo",
            "dias_prazo",
            "perito_atribuido",
            "created_by",
            "esta_finalizada",
            "classificacao",  # <--- 🔥 OBRIGATÓRIO ADICIONAR AQUI TAMBÉM
        ]

    def get_status_prazo(self, obj):
        if obj.data_finalizacao:
            return "CONCLUIDO"
        dias_corridos = (timezone.now().date() - obj.created_at.date()).days
        if dias_corridos <= 10:
            return "NO_PRAZO"
        elif dias_corridos <= 20:
            return "PRORROGADO"
        else:
            return "ATRASADO"

    def get_dias_prazo(self, obj):
        if obj.data_finalizacao:
            dias_totais = (obj.data_finalizacao.date() - obj.created_at.date()).days
            return f"Concluído em {dias_totais} dias"
        dias_corridos = (timezone.now().date() - obj.created_at.date()).days
        return f"{dias_corridos} dias corridos"


class OcorrenciaDetailSerializer(serializers.ModelSerializer):
    # ... (código sem alteração)
    servico_pericial = ServicoPericialSerializer(read_only=True)
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)
    autoridade = AutoridadeSerializer(read_only=True)
    cidade = CidadeSerializer(read_only=True)
    endereco = EnderecoOcorrenciaSerializer(read_only=True)
    classificacao = ClassificacaoOcorrenciaSerializer(read_only=True)
    procedimento_cadastrado = ProcedimentoCadastradoSerializer(read_only=True)
    tipo_documento_origem = TipoDocumentoSerializer(read_only=True)
    perito_atribuido = UserNestedSerializer(read_only=True)
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)
    exames_solicitados = ExameNestedSerializer(many=True, read_only=True)
    finalizada_por = UserNestedSerializer(read_only=True)
    reaberta_por = UserNestedSerializer(read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "numero_ocorrencia",
            "status",
            "servico_pericial",
            "unidade_demandante",
            "autoridade",
            "cidade",
            "classificacao",
            "procedimento_cadastrado",
            "tipo_documento_origem",
            "perito_atribuido",
            "exames_solicitados",
            "created_by",
            "updated_by",
            "finalizada_por",
            "reaberta_por",
            "data_fato",
            "hora_fato",
            "historico",
            "historico_ultima_edicao",
            "numero_documento_origem",
            "data_documento_origem",
            "processo_sei_numero",
            "data_finalizacao",
            "data_assinatura_finalizacao",
            "ip_assinatura_finalizacao",
            "data_reabertura",
            "motivo_reabertura",
            "ip_reabertura",
            "created_at",
            "updated_at",
            "endereco",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = request.user if request and hasattr(request, "user") else None

        if user and not user.is_superuser and "servico_pericial_id" in self.fields:
            servicos_do_usuario = user.servicos_periciais.all()
            self.fields["servico_pericial_id"].queryset = servicos_do_usuario

    def validate(self, data):
        if not self.instance and data:
            user = self.context["request"].user
            servico_pericial = data.get("servico_pericial")
            if (
                servico_pericial
                and not user.servicos_periciais.filter(pk=servico_pericial.pk).exists()
                and not user.is_superuser
            ):
                raise serializers.ValidationError(
                    {
                        "servico_pericial_id": (
                            "Você não tem permissão para registrar ocorrências "
                            "neste serviço pericial."
                        )
                    }
                )
        return data


class OcorrenciaUpdateSerializer(serializers.ModelSerializer):
    # ... (código sem alteração)
    perito_atribuido_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(perfil="PERITO"),
        source="perito_atribuido",
        required=False,
        allow_null=True,
        label="Perito Atribuído",
    )
    tipo_documento_origem_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoDocumento.objects.all(),
        source="tipo_documento_origem",
        required=False,
        allow_null=True,
        label="Tipo de Documento",
    )
    procedimento_cadastrado_id = serializers.PrimaryKeyRelatedField(
        queryset=ProcedimentoCadastrado.objects.all(),
        source="procedimento_cadastrado",
        required=False,
        allow_null=True,
        label="Procedimento",
    )
    classificacao_id = serializers.PrimaryKeyRelatedField(
        queryset=ClassificacaoOcorrencia.objects.all(),
        source="classificacao",
        required=False,
        label="Classificação",
    )
    unidade_demandante_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadeDemandante.objects.all(),
        source="unidade_demandante",
        required=False,
        label="Unidade Demandante",
    )
    autoridade_id = serializers.PrimaryKeyRelatedField(
        queryset=Autoridade.objects.all(),
        source="autoridade",
        required=False,
        label="Autoridade",
    )
    cidade_id = serializers.PrimaryKeyRelatedField(
        queryset=Cidade.objects.all(), source="cidade", required=False, label="Cidade"
    )
    exames_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text="Lista de IDs dos exames (substitui todos os existentes)",
    )
    exames_solicitados = ExameNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            "classificacao_id",
            "unidade_demandante_id",
            "autoridade_id",
            "cidade_id",
            "historico",
            "processo_sei_numero",
            "numero_documento_origem",
            "data_documento_origem",
            "tipo_documento_origem_id",
            "procedimento_cadastrado_id",
            "perito_atribuido_id",
            "exames_ids",
            "exames_solicitados",
        ]

    def validate_exames_ids(self, value):
        if not value:
            return value
        from exames.models import Exame

        existing_ids = list(
            Exame.objects.filter(id__in=value).values_list("id", flat=True)
        )
        invalid_ids = set(value) - set(existing_ids)
        if invalid_ids:
            raise serializers.ValidationError(f"Exames inválidos: {list(invalid_ids)}")
        return value

    def validate(self, data):
        instance = self.instance
        request = self.context.get("request")
        user = request.user
        # ===== VALIDAÇÃO GERAL: Se tem perito, só ele ou super admin editam =====
        if instance.perito_atribuido:
            if not user.is_superuser and user.id != instance.perito_atribuido.id:
                perito_nome = instance.perito_atribuido.nome_completo
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            f"🔒 Acesso Restrito: Esta ocorrência está atribuída ao perito {perito_nome}.",
                            "Apenas o perito atribuído ou um Super Administrador podem editar esta ocorrência.",
                            "Se necessário, solicite que o perito atribuído faça a alteração ou contate um administrador.",
                        ]
                    }
                )

        # --- INÍCIO DA CORREÇÃO ---
        classificacao = data.get("classificacao")
        if classificacao and classificacao.subgrupos.exists():
            raise serializers.ValidationError(
                f'A classificação "{classificacao.nome}" é um Grupo Principal. Por favor, selecione um subgrupo específico.'
            )
        # --- FIM DA CORREÇÃO ---

        if instance.esta_finalizada:
            raise serializers.ValidationError(
                "Esta ocorrência está finalizada e não pode ser editada."
            )

        if "exames_ids" in data:
            if instance.perito_atribuido:
                if not user.is_superuser and user.id != instance.perito_atribuido.id:
                    raise serializers.ValidationError(
                        {
                            "exames_ids": (
                                "Apenas o perito atribuído pode alterar os exames "
                                "desta ocorrência."
                            )
                        }
                    )

        if not user.is_superuser:
            if (
                instance.perito_atribuido
                and "perito_atribuido" in data
                and instance.perito_atribuido != data.get("perito_atribuido")
            ):
                raise serializers.ValidationError(
                    ("Apenas um Super Admin pode alterar um perito já " "atribuído.")
                )

            if "historico" in data and data.get("historico") != instance.historico:
                data_base_prazo = (
                    instance.historico_ultima_edicao or instance.created_at
                )
                if data_base_prazo:
                    prazo_edicao = data_base_prazo + datetime.timedelta(hours=72)
                    if timezone.now() > prazo_edicao:
                        raise serializers.ValidationError(
                            {
                                "historico": "Prazo de 72 horas para edição do histórico expirou."
                            }
                        )
        return data

    def update(self, instance, validated_data):
        if "procedimento_cadastrado" in validated_data:
            novo_procedimento = validated_data.get("procedimento_cadastrado")
            procedimento_atual = instance.procedimento_cadastrado
            if procedimento_atual and novo_procedimento != procedimento_atual:
                user = self.context["request"].user
                if not user.is_superuser:
                    raise serializers.ValidationError(
                        {
                            "procedimento_cadastrado": (
                                "Esta ocorrência já possui um procedimento vinculado. "
                                "Use o endpoint /vincular_procedimento/ ou "
                                "contate um administrador."
                            )
                        }
                    )

        exames_ids = validated_data.pop("exames_ids", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if exames_ids is not None:
            instance.exames_solicitados.set(exames_ids)
        return instance


class FinalizarComAssinaturaSerializer(serializers.Serializer):
    # ... (código sem alteração)
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        label="Senha",
        help_text=("Confirme sua senha para assinatura digital"),
    )

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user
        if not user.check_password(attrs.get("password")):
            raise serializers.ValidationError({"password": "Senha incorreta."})
        return attrs


class ReabrirOcorrenciaSerializer(serializers.Serializer):
    # ... (código sem alteração)
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        label="Senha",
        help_text="Confirme sua senha",
    )
    motivo_reabertura = serializers.CharField(
        max_length=1000, label="Motivo da Reabertura"
    )

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user
        if not user.check_password(attrs.get("password")):
            raise serializers.ValidationError({"password": "Senha incorreta."})
        if not attrs.get("motivo_reabertura", "").strip():
            raise serializers.ValidationError(
                {"motivo_reabertura": "O motivo da reabertura é obrigatório."}
            )
        return attrs


class OcorrenciaLixeiraSerializer(serializers.ModelSerializer):
    # ... (código sem alteração)
    servico_pericial = ServicoPericialSerializer(read_only=True)
    unidade_demandante = UnidadeDemandanteSerializer(read_only=True)
    deleted_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "numero_ocorrencia",
            "servico_pericial",
            "unidade_demandante",
            "deleted_at",
            "deleted_by",
        ]
        read_only_fields = ["deleted_at", "deleted_by"]


class OcorrenciaDisplaySerializer(serializers.ModelSerializer):
    # Fields for displaying Ocorrencia details
    servico_pericial = serializers.CharField(
        source="servico_pericial.nome", read_only=True
    )
    unidade_demandante = serializers.CharField(
        source="unidade_demandante.nome", read_only=True
    )
    autoridade = serializers.CharField(source="autoridade.nome", read_only=True)
    cidade = serializers.CharField(source="cidade.nome", read_only=True)
    classificacao = serializers.CharField(source="classificacao.nome", read_only=True)
    procedimento = serializers.SerializerMethodField()
    tipo_documento = serializers.CharField(
        source="tipo_documento_origem.nome", read_only=True
    )
    perito = serializers.CharField(
        source="perito_atribuido.nome_completo", read_only=True
    )
    data_criacao = serializers.DateTimeField(source="created_at", read_only=True)

    def get_procedimento(self, obj):
        if obj.procedimento_cadastrado:
            return (
                f"{obj.procedimento_cadastrado.tipo_procedimento.sigla} - "
                f"{obj.procedimento_cadastrado.numero}/"
                f"{obj.procedimento_cadastrado.ano}"
            )
        return None

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "numero_ocorrencia",
            "status",
            "servico_pericial",
            "unidade_demandante",
            "autoridade",
            "cidade",
            "classificacao",
            "procedimento",
            "tipo_documento",
            "perito",
            "data_fato",
            "hora_fato",
            "historico",
            "numero_documento_origem",
            "data_documento_origem",
            "processo_sei_numero",
            "data_criacao",
        ]


class OcorrenciaCreateSerializer(serializers.ModelSerializer):
    # ... (outros campos sem alteração)
    servico_pericial_id = serializers.PrimaryKeyRelatedField(
        queryset=ServicoPericial.objects.all(),
        source="servico_pericial",
        label="Serviço Pericial",
    )
    unidade_demandante_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadeDemandante.objects.all(),
        source="unidade_demandante",
        label="Unidade Demandante",
    )
    autoridade_id = serializers.PrimaryKeyRelatedField(
        queryset=Autoridade.objects.all(), source="autoridade", label="Autoridade"
    )
    cidade_id = serializers.PrimaryKeyRelatedField(
        queryset=Cidade.objects.all(), source="cidade", label="Cidade"
    )
    classificacao_id = serializers.PrimaryKeyRelatedField(
        queryset=ClassificacaoOcorrencia.objects.all(),  # Mantém all() para a validação inicial
        source="classificacao",
        label="Classificação",
    )
    procedimento_cadastrado_id = serializers.PrimaryKeyRelatedField(
        queryset=ProcedimentoCadastrado.objects.all(),
        source="procedimento_cadastrado",
        required=False,
        allow_null=True,
        label="Procedimento",
    )
    tipo_documento_origem_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoDocumento.objects.all(),
        source="tipo_documento_origem",
        required=False,
        allow_null=True,
        label="Tipo de Documento",
    )
    perito_atribuido_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(perfil="PERITO"),
        source="perito_atribuido",
        required=False,
        allow_null=True,
        label="Perito Atribuído",
    )

    class Meta:
        model = Ocorrencia
        fields = [
            "data_fato",
            "hora_fato",
            "historico",
            "numero_documento_origem",
            "data_documento_origem",
            "processo_sei_numero",
            "servico_pericial_id",
            "unidade_demandante_id",
            "autoridade_id",
            "cidade_id",
            "classificacao_id",
            "procedimento_cadastrado_id",
            "tipo_documento_origem_id",
            "perito_atribuido_id",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = request.user if request and hasattr(request, "user") else None
        if user and not user.is_superuser:
            servicos_do_usuario = user.servicos_periciais.all()
            self.fields["servico_pericial_id"].queryset = servicos_do_usuario

    def validate_exames_ids(self, value):
        if not value:
            return value
        from exames.models import Exame

        existing_ids = list(
            Exame.objects.filter(id__in=value).values_list("id", flat=True)
        )
        invalid_ids = set(value) - set(existing_ids)
        if invalid_ids:
            raise serializers.ValidationError(f"Exames inválidos: {list(invalid_ids)}")
        return value

    def validate(self, data):
        user = self.context["request"].user

        # --- INÍCIO DA CORREÇÃO ---
        classificacao = data.get("classificacao")
        if classificacao and classificacao.subgrupos.exists():
            raise serializers.ValidationError(
                f'A classificação "{classificacao.nome}" é um Grupo Principal. Por favor, selecione um subgrupo específico.'
            )
        # --- FIM DA CORREÇÃO ---

        if (
            not user.servicos_periciais.filter(
                pk=data.get("servico_pericial").pk
            ).exists()
            and not user.is_superuser
        ):
            raise serializers.ValidationError(
                {
                    "servico_pericial_id": "Você não tem permissão para registrar ocorrências neste serviço pericial."
                }
            )
        return data

    def create(self, validated_data):
        exames_ids = validated_data.pop("exames_ids", [])
        ocorrencia = Ocorrencia.objects.create(**validated_data)
        if exames_ids:
            ocorrencia.exames_solicitados.set(exames_ids)
        return ocorrencia
