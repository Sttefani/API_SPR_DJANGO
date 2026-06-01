# custodia/models.py

from django.db import models
from django.conf import settings
from usuarios.models import AuditModel


class Vestigio(AuditModel):

    class Status(models.TextChoices):
        INICIAL = 'INICIAL', 'Inicial'
        ANDAMENTO = 'ANDAMENTO', 'Em Andamento'
        FINALIZADO = 'FINALIZADO', 'Finalizado'

    lacre = models.CharField(max_length=255, blank=True, null=True)
    num_processo_sei = models.CharField(max_length=255, blank=True, null=True)
    conformidade = models.BooleanField(default=False)
    biologico = models.BooleanField(default=False)
    ocorrencia = models.CharField(max_length=255, blank=True, null=True)
    ano_ocorrencia = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.INICIAL
    )
    descricao = models.TextField(max_length=3000, blank=True, null=True)
    saiu_da_custodia = models.BooleanField(default=False)

    unidade_demandante = models.ForeignKey(
        'unidades_demandantes.UnidadeDemandante',
        on_delete=models.PROTECT,
        related_name='vestigios',
    )
    servico_pericial = models.ForeignKey(
        'servicos_periciais.ServicoPericial',
        on_delete=models.PROTECT,
        related_name='vestigios',
    )
    autoridade = models.ForeignKey(
        'autoridades.Autoridade',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vestigios',
    )
    user_destino = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vestigios_destino',
    )
    procedimentos = models.ManyToManyField(
        'procedimentos_cadastrados.ProcedimentoCadastrado',
        blank=True,
        related_name='vestigios_custodia',
    )
    # Vinculação com Ocorrências do módulo de análise criminal.
    # Opcional: um vestígio pode existir sem ocorrência vinculada.
    # M2M porque um vestígio pode aparecer em N ocorrências de serviços distintos.
    ocorrencias_vinculadas = models.ManyToManyField(
        'ocorrencias.Ocorrencia',
        blank=True,
        related_name='vestigios',
        verbose_name='Ocorrências Vinculadas',
    )
    vestigio_contra_prova = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contra_provas',
    )

    # Fallback de não repúdio para o registro inicial
    responsavel_nome = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Nome do responsável pelo registro — usado quando created_by não está disponível.'
    )

    def get_responsavel(self) -> str:
        if self.created_by:
            return self.created_by.nome_completo
        return self.responsavel_nome or '—'

    def __str__(self):
        return f"Vestígio #{self.pk} — {self.lacre or 'sem lacre'}"

    class Meta:
        verbose_name = "Vestígio"
        verbose_name_plural = "Vestígios"
        ordering = ['-created_at']


class VestigioMovimentacao(AuditModel):

    vestigio = models.ForeignKey(
        Vestigio,
        on_delete=models.CASCADE,
        related_name='movimentacoes_custodia',
    )
    lacre = models.CharField(max_length=255, blank=True, null=True)
    num_processo_sei = models.CharField(max_length=255, blank=True, null=True)
    descricao = models.TextField(max_length=3000, blank=True, null=True)

    unidade_demandante = models.ForeignKey(
        'unidades_demandantes.UnidadeDemandante',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimentacoes_custodia',
    )
    servico_pericial = models.ForeignKey(
        'servicos_periciais.ServicoPericial',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimentacoes_custodia',
    )
    autoridade = models.ForeignKey(
        'autoridades.Autoridade',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimentacoes_custodia',
    )
    user_destino = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimentacoes_custodia_destino',
    )

    aceito = models.BooleanField(default=False)
    data_hora_aceito = models.DateTimeField(null=True, blank=True)

    # Fallback de não repúdio: nome do operador quando o usuário Django
    # não existe (ex.: importação de dados históricos do Custódia Java).
    # Preenchido automaticamente pelo ETL; NULL para registros novos.
    responsavel_nome = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Nome do responsável — usado quando created_by não está disponível.'
    )

    def get_responsavel(self) -> str:
        """Retorna o nome do responsável, priorizando o usuário Django."""
        if self.created_by:
            return self.created_by.nome_completo
        return self.responsavel_nome or '—'

    def __str__(self):
        return f"Movimentação #{self.pk} — Vestígio #{self.vestigio_id}"

    class Meta:
        verbose_name = "Movimentação de Vestígio"
        verbose_name_plural = "Movimentações de Vestígios"
        ordering = ['-created_at']


class DNA(AuditModel):

    class SimNao(models.TextChoices):
        SIM = 'YES', 'Sim'
        NAO = 'NO', 'Não'

    class FinalidadeColeta(models.TextChoices):
        LEI = 'LEI', 'Lei 12.654/2012'
        DJ = 'DJ', 'Decisão Judicial'

    class Situacao(models.TextChoices):
        APENADO = 'APENADO', 'Apenado'
        NAO_APENADO = 'NAO_APENADO', 'Não Apenado'

    UF_CHOICES = [
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'),
        ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'),
        ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'), ('MG', 'Minas Gerais'),
        ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'), ('PE', 'Pernambuco'),
        ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'),
        ('SC', 'Santa Catarina'), ('SP', 'São Paulo'), ('SE', 'Sergipe'),
        ('TO', 'Tocantins'),
    ]

    nome = models.CharField(max_length=255)
    nascimento = models.DateTimeField()
    naturalidade = models.CharField(max_length=255)
    estrangeiro = models.BooleanField(default=False)
    uf = models.CharField(max_length=2, choices=UF_CHOICES, blank=True, null=True)
    mae = models.CharField(max_length=255)
    pai = models.CharField(max_length=255, blank=True, null=True)
    cpf = models.CharField(max_length=14)
    rg = models.CharField(max_length=30)
    nome_foto = models.CharField(max_length=255, blank=True, null=True)   # legado Java
    foto = models.ImageField(
        upload_to='custodia/dna/fotos/',
        blank=True, null=True,
        help_text='Fotografia do coletado (JPG/PNG). Opcional.',
    )
    gemeo = models.CharField(max_length=3, choices=SimNao.choices)
    transfusao = models.CharField(max_length=3, choices=SimNao.choices)
    transplante = models.CharField(max_length=3, choices=SimNao.choices)
    processado_banco_perfis_genetico = models.CharField(max_length=3, choices=SimNao.choices)
    unidade_prisional = models.CharField(max_length=255, blank=True, null=True)
    tipo_penal = models.CharField(max_length=255, blank=True, null=True)
    data_da_coleta = models.DateTimeField()
    lacres = models.CharField(max_length=255, blank=True, null=True)
    testemunha = models.CharField(max_length=255, blank=True, null=True)
    testemunha2 = models.CharField(max_length=255, blank=True, null=True)
    notas = models.TextField(max_length=2000, blank=True, null=True)
    pais = models.CharField(max_length=100, blank=True, null=True)
    ocorrencia = models.CharField(max_length=255, blank=True, null=True)
    processo_judicial = models.CharField(max_length=255, blank=True, null=True)
    num_processo_sei = models.CharField(max_length=255, blank=True, null=True)
    finalidade_coleta = models.CharField(max_length=3, choices=FinalidadeColeta.choices)
    codigo_barras = models.CharField(max_length=100, blank=True, null=True)
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.NAO_APENADO
    )
    responsavel_coleta = models.CharField(max_length=255, blank=True, null=True)
    registrado_por_usuario_externo = models.BooleanField(default=False)

    perito = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dnas_como_perito',
    )
    vestigio = models.ForeignKey(
        Vestigio,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dnas',
    )

    def __str__(self):
        return f"DNA — {self.nome} ({self.cpf})"

    class Meta:
        verbose_name = "DNA"
        verbose_name_plural = "DNAs"
        ordering = ['-created_at']
