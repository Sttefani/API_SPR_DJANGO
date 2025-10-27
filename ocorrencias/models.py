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
    exames_solicitados = models.ManyToManyField(
        Exame, blank=True, verbose_name="Exames Solicitados"
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

        # Validação: Já finalizada
        if self.esta_finalizada:
            raise ValidationError(
                f"Esta ocorrência já foi finalizada por {self.finalizada_por.nome_completo} "
                f"em {self.data_finalizacao.strftime('%d/%m/%Y às %H:%M')}."
            )

        # Validação: Perito obrigatório
        if not self.perito_atribuido:
            raise ValidationError(
                "Não é possível finalizar uma ocorrência sem perito atribuído. "
                "Atribua um perito responsável primeiro."
            )

        # Validação: Status correto
        if self.status != self.Status.EM_ANALISE:
            raise ValidationError(
                f"Apenas ocorrências com status 'Em Análise' podem ser finalizadas. "
                f"Status atual: {self.get_status_display()}."
            )

        # Validação: User válido
        if not user or not user.is_authenticated:
            raise ValidationError("Usuário inválido para assinatura digital.")

        # Validação: Perfil autorizado
        if not (user.perfil in ["ADMINISTRATIVO", "SUPER_ADMIN"] or user.is_superuser):
            raise ValidationError(
                f"Usuário {user.nome_completo} não tem permissão para finalizar ocorrências."
            )

        # Validação: IP obrigatório
        if not ip_address:
            ip_address = "127.0.0.1"

        # Realiza a finalização
        self.status = self.Status.FINALIZADA
        self.data_finalizacao = timezone.now()
        self.finalizada_por = user
        self.data_assinatura_finalizacao = timezone.now()
        self.ip_assinatura_finalizacao = ip_address
        self.save()

    def reabrir(self, user, motivo, ip_address):
        """Reabre uma ocorrência finalizada."""
        from django.core.exceptions import ValidationError

        # Validação: Deve estar finalizada
        if not self.esta_finalizada:
            raise ValidationError(
                "Esta ocorrência não está finalizada. Apenas ocorrências finalizadas podem ser reabertas."
            )

        # Validação: Motivo obrigatório
        if not motivo or not motivo.strip():
            raise ValidationError(
                "O motivo da reabertura é obrigatório. Por favor, forneça uma justificativa detalhada."
            )

        if len(motivo.strip()) < 10:
            raise ValidationError(
                "O motivo da reabertura é muito curto. Por favor, forneça uma justificativa mais detalhada (mínimo 10 caracteres)."
            )

        # Validação: User válido e Super Admin
        if not user or not user.is_authenticated:
            raise ValidationError("Usuário inválido para reabertura.")

        if not user.is_superuser:
            raise ValidationError(
                f"Usuário {user.nome_completo} não tem permissão para reabrir ocorrências. Apenas Super Administradores podem reabrir ocorrências finalizadas."
            )

        # Validação: IP obrigatório
        if not ip_address:
            ip_address = "127.0.0.1"

        # Realiza a reabertura
        self.status = self.Status.EM_ANALISE
        self.data_finalizacao = None
        self.reaberta_por = user
        self.data_reabertura = timezone.now()
        self.motivo_reabertura = motivo.strip()
        self.ip_reabertura = ip_address
        self.save()

    # ===== MÉTODO SAVE CORRIGIDO =====
    def save(self, *args, **kwargs):
        # ===== GERAÇÃO DO NÚMERO DA OCORRÊNCIA (NOVA LÓGICA COM LOCK) =====
        if not self.pk:
            with transaction.atomic():
                now = datetime.datetime.now()
                servico_sigla = self.servico_pericial.sigla
                timestamp_base = now.strftime("%Y%m%d%H%M%S")

                # Número no formato original
                self.numero_ocorrencia = f"{timestamp_base}/{servico_sigla}"

                # Tenta salvar até 10 vezes (caso haja duplicação rara)
                tentativas = 0
                max_tentativas = 10

                while tentativas < max_tentativas:
                    try:
                        # Tenta salvar com o número gerado
                        self._executar_save(args, kwargs)
                        return  # ✅ Sucesso! Sai do método

                    except IntegrityError as e:
                        # Se for erro de número duplicado, adiciona sufixo
                        if "numero_ocorrencia" in str(e) or "unique" in str(e).lower():
                            tentativas += 1
                            nano = int(time.time() * 1000000) % 1000000
                            self.numero_ocorrencia = (
                                f"{timestamp_base}/{servico_sigla}-{nano + tentativas}"
                            )
                        else:
                            # Se for outro tipo de IntegrityError, propaga
                            raise

                # Se após 10 tentativas não conseguiu, levanta erro
                raise IntegrityError(
                    f"Não foi possível gerar número único após {max_tentativas} tentativas"
                )

        # ===== PARA ATUALIZAÇÕES (quando já tem PK) =====
        else:
            self._executar_save(args, kwargs)

    def _executar_save(self, args, kwargs):
        """
        Método auxiliar que executa toda a lógica de save
        (separado para evitar duplicação de código)
        """
        # ===== ATUALIZAÇÃO DO HISTÓRICO =====
        if self.pk:
            try:
                versao_antiga = Ocorrencia.objects.get(pk=self.pk)
                if versao_antiga.historico != self.historico:
                    self.historico_ultima_edicao = timezone.now()
            except Ocorrencia.DoesNotExist:
                pass

        # ===== LÓGICA DE STATUS =====
        if self.status != self.Status.FINALIZADA:
            if self.perito_atribuido:
                self.status = self.Status.EM_ANALISE
            else:
                self.status = self.Status.AGUARDANDO_PERITO

        # ===== NORMALIZAÇÃO DE CAMPOS =====
        if self.numero_documento_origem:
            self.numero_documento_origem = self.numero_documento_origem.upper()
        if self.processo_sei_numero:
            self.processo_sei_numero = self.processo_sei_numero.upper()

        # ===== SALVA NO BANCO =====
        super(Ocorrencia, self).save(*args, **kwargs)

    def __str__(self):
        return self.numero_ocorrencia

    class Meta:
        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências"
        ordering = ["-created_at"]


# --- INÍCIO DO NOVO CÓDIGO (SEGURO E ADITIVO) ---


class HistoricoVinculacao(models.Model):
    """
    Modelo para registrar (auditar) a troca de um procedimento vinculado a uma ocorrência.
    Esta tabela serve como um log, garantindo a rastreabilidade das alterações.
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
