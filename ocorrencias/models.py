# ocorrencias/models.py

import datetime
from django.db import models
from django.conf import settings

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
        AGUARDANDO_PERITO = 'AGUARDANDO_PERITO', 'Aguardando Atribuição de Perito'
        EM_ANALISE = 'EM_ANALISE', 'Em Análise'
        FINALIZADA = 'FINALIZADA', 'Finalizada'

    numero_ocorrencia = models.CharField(
        max_length=30, unique=True, editable=False, verbose_name="Número da Ocorrência (OC)"
    )
    servico_pericial = models.ForeignKey(
        ServicoPericial, on_delete=models.PROTECT, related_name="ocorrencias", verbose_name="Serviço Pericial"
    )
    unidade_demandante = models.ForeignKey(
        UnidadeDemandante, on_delete=models.PROTECT, related_name="ocorrencias", verbose_name="Unidade Demandante"
    )
    autoridade = models.ForeignKey(
        Autoridade, on_delete=models.PROTECT, related_name="ocorrencias", verbose_name="Autoridade Demandante"
    )
    data_fato = models.DateField(verbose_name="Data do Fato")
    hora_fato = models.TimeField(null=True, blank=True, verbose_name="Hora do Fato")
    cidade = models.ForeignKey(Cidade, on_delete=models.PROTECT, related_name="ocorrencias",
                               verbose_name="Cidade do Fato")
    classificacao = models.ForeignKey(
        ClassificacaoOcorrencia, on_delete=models.PROTECT, related_name="ocorrencias",
        verbose_name="Classificação da Ocorrência"
    )
    procedimento_cadastrado = models.ForeignKey(
        ProcedimentoCadastrado, on_delete=models.SET_NULL, null=True, blank=True, related_name="ocorrencias",
        verbose_name="Procedimento"
    )
    tipo_documento_origem = models.ForeignKey(
        TipoDocumento, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tipo de Documento de Origem"
    )
    numero_documento_origem = models.CharField(max_length=50, null=True, blank=True,
                                               verbose_name="Número do Documento de Origem")
    ano_documento_origem = models.PositiveIntegerField(null=True, blank=True, verbose_name="Ano do Documento de Origem")
    data_documento_origem = models.DateField(null=True, blank=True, verbose_name="Data do Documento de Origem")

    # NOVO CAMPO ADICIONADO AQUI
    processo_sei_numero = models.CharField(
        max_length=50, null=True, blank=True, verbose_name="Número do Processo SEI"
    )

    perito_atribuido = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ocorrencias_atribuidas",
        verbose_name="Perito Atribuído",
        limit_choices_to={'perfil': 'PERITO'}
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AGUARDANDO_PERITO,
        verbose_name="Status da Ocorrência"
    )
    data_finalizacao = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Finalização"
    )
    exames_solicitados = models.ManyToManyField(
        Exame,
        blank=True,
        verbose_name="Exames Solicitados"
    )
    historico = models.TextField(
        blank=True, null=True, verbose_name="Histórico/Observações"
    )
    historico_ultima_edicao = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name="Última Edição do Histórico"
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            now = datetime.datetime.now()
            servico_sigla = self.servico_pericial.sigla
            timestamp = now.strftime('%Y%m%d%H%M%S')
            self.numero_ocorrencia = f"{timestamp}/{servico_sigla}"

        if self.numero_documento_origem:
            self.numero_documento_origem = self.numero_documento_origem.upper()

        # NOVA LÓGICA DE CAIXA ALTA
        if self.processo_sei_numero:
            self.processo_sei_numero = self.processo_sei_numero.upper()

        if self.pk:
            try:
                versao_antiga = Ocorrencia.objects.get(pk=self.pk)
                if versao_antiga.historico != self.historico:
                    self.historico_ultima_edicao = datetime.datetime.now()
            except Ocorrencia.DoesNotExist:
                pass

            if self.perito_atribuido and self.status == self.Status.AGUARDANDO_PERITO:
                self.status = self.Status.EM_ANALISE
            elif not self.perito_atribuido and self.status != self.Status.FINALIZADA:
                self.status = self.Status.AGUARDANDO_PERITO

        super(Ocorrencia, self).save(*args, **kwargs)

    def __str__(self):
        return self.numero_ocorrencia

    class Meta:
        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências"
        ordering = ['-created_at']