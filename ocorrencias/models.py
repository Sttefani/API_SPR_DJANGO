# ocorrencias/models.py

import datetime
from django.db import models, transaction, IntegrityError
from django.conf import settings
from django.utils import timezone
import time

# Importando os modelos dos nossos outros apps
from usuarios.models import AuditModel
from servicos_periciais.models import ServicoPericial
from unidades_demandantes.models import UnidadeDemandante
from procedimentos_cadastrados.models import ProcedimentoCadastrado
from tipos_documento.models import TipoDocumento
from cidades.models import Cidade
from autoridades.models import Autoridade
from classificacoes.models import ClassificacaoOcorrencia
from exames.models import Exame


# ============================================================================
# NOVO MODEL: Controle de Sequencial Mensal
# ============================================================================
class SequencialOcorrencia(models.Model):
    """
    Controla o sequencial de numeração das ocorrências por ano.
    """

    ano = models.PositiveSmallIntegerField(unique=True, verbose_name="Ano (2 dígitos)")
    ultimo_sequencial = models.PositiveIntegerField(
        default=0, verbose_name="Último Sequencial"
    )

    class Meta:
        verbose_name = "Sequencial de Ocorrência"
        verbose_name_plural = "Sequenciais de Ocorrências"

    def __str__(self):
        return f"Ano 20{self.ano:02d} - Último sequencial: {self.ultimo_sequencial}"


# ============================================================================
# MODEL NOVO: Tabela Intermediária de Exames (Aceita Quantidade)
# ============================================================================
class OcorrenciaExame(models.Model):
    ocorrencia = models.ForeignKey("Ocorrencia", on_delete=models.CASCADE)
    exame = models.ForeignKey(Exame, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=1, verbose_name="Quantidade")

    class Meta:
        db_table = "ocorrencias_ocorrencia_exames_qtd"
        unique_together = [("ocorrencia", "exame")]
        verbose_name = "Exame da Ocorrência"
        verbose_name_plural = "Exames da Ocorrência"

    def __str__(self):
        return f"{self.exame.nome} (Qtd: {self.quantidade})"


# ============================================================================
# MODEL PRINCIPAL: Ocorrência
# ============================================================================
class Ocorrencia(AuditModel):
    class Status(models.TextChoices):
        AGUARDANDO_PERITO = "AGUARDANDO_PERITO", "Aguardando Atribuição de Perito"
        EM_ANALISE = "EM_ANALISE", "Em Análise"
        FINALIZADA = "FINALIZADA", "Finalizada"

    numero_ocorrencia = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        verbose_name="Número da Ocorrência (OC)",
    )
    servico_pericial = models.ForeignKey(
        ServicoPericial,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="Serviço Pericial",
    )
    unidade_demandante = models.ForeignKey(
        UnidadeDemandante,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="Unidade Demandante",
    )
    autoridade = models.ForeignKey(
        Autoridade,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="Autoridade Demandante",
    )
    data_fato = models.DateField(verbose_name="Data do Fato", null=True, blank=True)
    hora_fato = models.TimeField(null=True, blank=True, verbose_name="Hora do Fato")
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="Cidade do Fato",
    )
    classificacao = models.ForeignKey(
        ClassificacaoOcorrencia,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="Classificação da Ocorrência",
    )
    procedimento_cadastrado = models.ForeignKey(
        ProcedimentoCadastrado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias",
        verbose_name="Procedimento",
    )
    tipo_documento_origem = models.ForeignKey(
        TipoDocumento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tipo de Documento de Origem",
    )
    numero_documento_origem = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Número do Documento de Origem",
    )
    data_documento_origem = models.DateField(
        null=True, blank=True, verbose_name="Data do Documento de Origem"
    )
    processo_sei_numero = models.CharField(
        max_length=50, null=True, blank=True, verbose_name="Número do Processo SEI"
    )
    perito_atribuido = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_atribuidas",
        verbose_name="Perito Atribuído",
        limit_choices_to={"perfil": "PERITO"},
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AGUARDANDO_PERITO,
        verbose_name="Status da Ocorrência",
    )
    data_finalizacao = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Finalização"
    )

    # =========================================================================
    # CAMPO DE EXAMES RECRIADO (AGORA COM THROUGH E QUANTIDADE)
    # =========================================================================
    exames_solicitados = models.ManyToManyField(
        Exame,
        through="OcorrenciaExame",
        blank=True,
        verbose_name="Exames Solicitados",
    )

    historico = models.TextField(
        blank=True, null=True, verbose_name="Histórico/Observações"
    )
    historico_ultima_edicao = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name="Última Edição do Histórico"
    )

    # CAMPOS DE ASSINATURA DIGITAL
    finalizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ocorrencias_finalizadas",
        null=True,
        blank=True,
        verbose_name="Finalizada por",
    )
    data_assinatura_finalizacao = models.DateTimeField(
        null=True, blank=True, verbose_name="Data/Hora da Assinatura"
    )
    ip_assinatura_finalizacao = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="IP da Assinatura"
    )
    reaberta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ocorrencias_reabertas",
        null=True,
        blank=True,
        verbose_name="Reaberta por",
    )
    data_reabertura = models.DateTimeField(
        null=True, blank=True, verbose_name="Data/Hora da Reabertura"
    )
    motivo_reabertura = models.TextField(
        blank=True, verbose_name="Motivo da Reabertura"
    )
    ip_reabertura = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="IP da Reabertura"
    )

    # PROPRIEDADES PARA ASSINATURA
    @property
    def esta_finalizada(self):
        return self.status == "FINALIZADA" and self.finalizada_por is not None

    @property
    def pode_ser_editada(self):
        return not self.esta_finalizada

    def finalizar_com_assinatura(self, user, ip_address):
        """Finaliza a ocorrência com assinatura digital."""
        from django.core.exceptions import ValidationError

        if self.esta_finalizada:
            raise ValidationError(
                f"Esta ocorrência já foi finalizada por {self.finalizada_por.nome_completo} "
                f"em {self.data_finalizacao.strftime('%d/%m/%Y às %H:%M')}."
            )
        if not self.perito_atribuido:
            raise ValidationError(
                "Não é possível finalizar uma ocorrência sem perito atribuído. "
                "Atribua um perito responsável primeiro."
            )
        if self.status != self.Status.EM_ANALISE:
            raise ValidationError(
                f"Apenas ocorrências com status 'Em Análise' podem ser finalizadas. "
                f"Status atual: {self.get_status_display()}."
            )
        if not user or not user.is_authenticated:
            raise ValidationError("Usuário inválido para assinatura digital.")
        if not (user.perfil in ["ADMINISTRATIVO", "SUPER_ADMIN"] or user.is_superuser):
            raise ValidationError(
                f"Usuário {user.nome_completo} não tem permissão para finalizar ocorrências."
            )
        if not ip_address:
            ip_address = "127.0.0.1"

        self.status = self.Status.FINALIZADA
        self.data_finalizacao = timezone.now()
        self.finalizada_por = user
        self.data_assinatura_finalizacao = timezone.now()
        self.ip_assinatura_finalizacao = ip_address
        self.save()

    def reabrir(self, user, motivo, ip_address):
        """Reabre uma ocorrência finalizada."""
        from django.core.exceptions import ValidationError

        if not self.esta_finalizada:
            raise ValidationError(
                "Esta ocorrência não está finalizada. Apenas ocorrências finalizadas podem ser reabertas."
            )
        if not motivo or not motivo.strip():
            raise ValidationError(
                "O motivo da reabertura é obrigatório. Por favor, forneça uma justificativa detalhada."
            )
        if len(motivo.strip()) < 10:
            raise ValidationError(
                "O motivo da reabertura é muito curto. Por favor, forneça uma justificativa mais detalhada (mínimo 10 caracteres)."
            )
        if not user or not user.is_authenticated:
            raise ValidationError("Usuário inválido para reabertura.")
        if not user.is_superuser:
            raise ValidationError(
                f"Usuário {user.nome_completo} não tem permissão para reabrir ocorrências. Apenas Super Administradores podem reabrir ocorrências finalizadas."
            )
        if not ip_address:
            ip_address = "127.0.0.1"

        self.status = self.Status.EM_ANALISE
        self.data_finalizacao = None
        self.reaberta_por = user
        self.data_reabertura = timezone.now()
        self.motivo_reabertura = motivo.strip()
        self.ip_reabertura = ip_address
        self.save()

    # =========================================================================
    # MÉTODO SAVE COM NOVA LÓGICA DE NUMERAÇÃO
    # =========================================================================
    def save(self, *args, **kwargs):
        if not self.pk:
            with transaction.atomic():
                now = datetime.datetime.now()
                servico_sigla = self.servico_pericial.sigla
                ano_2digitos = now.year % 100
                mes = now.month

                (
                    sequencial_obj,
                    created,
                ) = SequencialOcorrencia.objects.select_for_update().get_or_create(
                    ano=ano_2digitos, defaults={"ultimo_sequencial": 0}
                )

                sequencial_obj.ultimo_sequencial += 1
                sequencial_obj.save()

                numero_base = (
                    f"{ano_2digitos:02d}{mes:02d}{sequencial_obj.ultimo_sequencial:05d}"
                )

                self.numero_ocorrencia = f"{numero_base}/{servico_sigla}"

                tentativas = 0
                max_tentativas = 10

                while tentativas < max_tentativas:
                    try:
                        self._executar_save(args, kwargs)
                        return
                    except IntegrityError as e:
                        if "numero_ocorrencia" in str(e) or "unique" in str(e).lower():
                            tentativas += 1
                            sequencial_obj.refresh_from_db()
                            sequencial_obj.ultimo_sequencial += 1
                            sequencial_obj.save()
                            numero_base = f"{ano_2digitos:02d}{mes:02d}{sequencial_obj.ultimo_sequencial:05d}"
                            self.numero_ocorrencia = f"{numero_base}/{servico_sigla}"
                        else:
                            raise
                raise IntegrityError(
                    f"Não foi possível gerar número único após {max_tentativas} tentativas"
                )
        else:
            self._executar_save(args, kwargs)

    def _executar_save(self, args, kwargs):
        if self.pk:
            try:
                versao_antiga = Ocorrencia.objects.get(pk=self.pk)
                if versao_antiga.historico != self.historico:
                    self.historico_ultima_edicao = timezone.now()
            except Ocorrencia.DoesNotExist:
                pass

        if self.status != self.Status.FINALIZADA:
            if self.perito_atribuido:
                self.status = self.Status.EM_ANALISE
            else:
                self.status = self.Status.AGUARDANDO_PERITO

        if self.numero_documento_origem:
            self.numero_documento_origem = self.numero_documento_origem.upper()
        if self.processo_sei_numero:
            self.processo_sei_numero = self.processo_sei_numero.upper()

        super(Ocorrencia, self).save(*args, **kwargs)

    def __str__(self):
        return self.numero_ocorrencia

    class Meta:
        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências"
        ordering = ["-created_at"]


# ============================================================================
# MODEL: Histórico de Vinculação (sem alterações)
# ============================================================================
class HistoricoVinculacao(models.Model):
    """
    Modelo para registrar (auditar) a troca de um procedimento vinculado a uma ocorrência.
    """

    ocorrencia = models.ForeignKey(
        Ocorrencia,
        on_delete=models.CASCADE,
        related_name="historico_vinculacao",
        verbose_name="Ocorrência Modificada",
    )
    procedimento_antigo = models.ForeignKey(
        ProcedimentoCadastrado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Procedimento Anterior",
    )
    procedimento_novo = models.ForeignKey(
        ProcedimentoCadastrado,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name="Procedimento Novo",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Usuário Responsável",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, verbose_name="Data e Hora da Alteração"
    )

    def __str__(self):
        return f"Log de {self.ocorrencia.numero_ocorrencia} em {self.timestamp.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        verbose_name = "Histórico de Vinculação"
        verbose_name_plural = "Históricos de Vinculação"
        ordering = ["-timestamp"]


from .endereco_models import EnderecoOcorrencia, TipoOcorrencia
