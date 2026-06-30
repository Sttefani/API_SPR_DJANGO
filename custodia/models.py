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
    motivo_finalizacao = models.TextField(max_length=2000, blank=True, null=True)

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
    # Serviço onde o vestígio foi CADASTRADO — origem imutável da cadeia de custódia.
    # NUNCA é alterado por movimentações (diferente de servico_pericial, que reflete a
    # localização/posse atual e muda no aceite). Nullable: registros históricos já
    # movimentados internamente tiveram a origem sobrescrita e não há como recuperá-la.
    servico_pericial_origem = models.ForeignKey(
        'servicos_periciais.ServicoPericial',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='vestigios_origem',
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

    def sincronizar_ocorrencia_principal(self):
        """
        Mantém os campos-texto `ocorrencia`/`ano_ocorrencia` espelhando a PRIMEIRA
        ocorrência vinculada (fonte única). Esses campos saíram do formulário de
        cadastro por serem redundantes com a vinculação (M2M), mas continuam
        alimentando a FAV e as listagens — então são preenchidos automaticamente
        a partir do vínculo. Limpa os campos quando não há ocorrência vinculada.
        """
        oc = self.ocorrencias_vinculadas.order_by('id').first()
        self.ocorrencia     = oc.numero_ocorrencia if oc else None
        self.ano_ocorrencia = self._extrair_ano_ocorrencia(oc) if oc else None
        self.save(update_fields=['ocorrencia', 'ano_ocorrencia'])

    @staticmethod
    def _extrair_ano_ocorrencia(oc):
        """
        Ano da ocorrência a partir do PRÓPRIO número (formato AAMMNNNNN/SIGLA —
        os 2 primeiros dígitos são o ano de registro, ex.: '26…' → 2026). O número
        é obrigatório, então é a fonte confiável. Cai para o ano de `data_fato`
        apenas quando o número foge do padrão (ex.: dados legados).
        """
        base = (oc.numero_ocorrencia or '').split('/')[0]
        if len(base) >= 2 and base[:2].isdigit():
            return 2000 + int(base[:2])
        return oc.data_fato.year if oc.data_fato else None

    def pode_editar_por_lotacao(self, user) -> bool:
        """
        Regra de edição (integridade da cadeia de custódia): alterar um vestígio
        antes da 1ª movimentação é ato restrito a quem está lotado no SERVIÇO
        PERICIAL onde ele foi cadastrado — não a administradores de outros
        serviços/unidades. SUPER_ADMIN mantém break-glass.

        Não verifica status/movimentações — isso é responsabilidade de quem chama
        (perform_update e get_pode_editar fazem essas checagens com mensagens próprias).
        """
        if getattr(user, 'is_superuser', False) or getattr(user, 'perfil', None) == 'SUPER_ADMIN':
            return True
        if not self.servico_pericial_id:
            return False
        return user.servicos_periciais.filter(id=self.servico_pericial_id).exists()

    def save(self, *args, **kwargs):
        # Lacre sempre em CAIXA ALTA no banco — independente de como foi digitado
        # (formulário, API direta, shell, importação). Garantia de última instância
        # da padronização forense; espelha o uppercase automático do modelo DNA.
        if self.lacre:
            self.lacre = self.lacre.strip().upper()

        # Carimba o serviço de ORIGEM apenas no cadastro (INSERT). `_state.adding`
        # é True somente antes do 1º save — em qualquer save posterior (ex.: aceite,
        # que altera servico_pericial para a localização atual) a origem é preservada.
        # Registros históricos carregados do banco têm adding=False → nunca são tocados.
        #
        # NÃO carimba para registro EXTERNO: ele não pertence a serviço pericial; o
        # serviço informado é o DESTINO (custódia central do IC), não a origem. Para
        # o EXTERNO, a origem é a unidade demandante (ver origem_display()).
        _externo = bool(self.created_by_id) and getattr(self.created_by, 'perfil', None) == 'EXTERNO'
        if (self._state.adding and self.servico_pericial_id
                and not self.servico_pericial_origem_id and not _externo):
            self.servico_pericial_origem_id = self.servico_pericial_id
        super().save(*args, **kwargs)

    def servicos_do_registrante(self) -> str:
        """
        Siglas dos serviços periciais do usuário que registrou (created_by),
        separadas por vírgula. '' quando não há registrante (dado ETL antigo) ou
        ele não tem serviços vinculados.
        """
        if not self.created_by_id:
            return ''
        sigs = list(self.created_by.servicos_periciais.values_list('sigla', flat=True))
        return ', '.join(sigs)

    def origem_display(self):
        """
        (texto, inferido) do serviço de ORIGEM para exibição:
        - serviço explícito gravado no cadastro → (nome, False)
        - sem registro explícito (dado histórico), mas o registrante tem serviço →
          infere do serviço dele → (siglas, True)
        - nada disponível → ('Não registrada', False)
        """
        if self.servico_pericial_origem_id:
            return (self.servico_pericial_origem.nome, False)
        servs = self.servicos_do_registrante()
        if servs:
            return (servs, True)
        # Registrado por EXTERNO → a origem é a UNIDADE demandante (delegacia/vara),
        # não um serviço pericial. O serviço dele é sempre o destino (custódia do IC).
        if self.created_by_id and getattr(self.created_by, 'perfil', None) == 'EXTERNO':
            return ('Origem externa (unidade demandante)', False)
        return ('Não registrada (anterior ao rastreio de origem)', False)

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

    def save(self, *args, **kwargs):
        # Lacre da movimentação sempre em CAIXA ALTA — mesma padronização do
        # Vestigio.lacre. Garante uppercase no histórico de lacres exibido na FAV,
        # independente de como o usuário digitou no toggle "Novo lacre? SIM".
        if self.lacre:
            self.lacre = self.lacre.strip().upper()
        super().save(*args, **kwargs)

    def pode_editar_por_lotacao(self, user) -> bool:
        """
        Edição de movimentação PENDENTE: restrita a quem está lotado no serviço
        de ORIGEM — o serviço que detém o vestígio (quem ENVIOU o passe). Como o
        aceite ainda não ocorreu, a localização atual do vestígio
        (vestigio.servico_pericial) É a origem. SUPER_ADMIN é break-glass;
        ADMINISTRATIVO NÃO tem override (mesma regra de Vestigio.pode_editar_por_lotacao).

        Não verifica aceito/finalizado — isso é responsabilidade de quem chama
        (perform_update e get_pode_editar fazem essas checagens com mensagens próprias).
        """
        if getattr(user, 'is_superuser', False) or getattr(user, 'perfil', None) == 'SUPER_ADMIN':
            return True
        origem_id = self.vestigio.servico_pericial_id
        if not origem_id:
            return False
        return user.servicos_periciais.filter(id=origem_id).exists()

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

    # Campos de texto livre que devem ser salvos em maiúsculas
    _CAMPOS_UPPERCASE = [
        'nome', 'naturalidade', 'mae', 'pai', 'rg',
        'unidade_prisional', 'tipo_penal', 'lacres',
        'testemunha', 'testemunha2', 'notas', 'pais',
        'ocorrencia', 'processo_judicial', 'num_processo_sei',
        'codigo_barras', 'responsavel_coleta',
    ]

    def save(self, *args, **kwargs):
        for campo in self._CAMPOS_UPPERCASE:
            valor = getattr(self, campo, None)
            if valor:
                setattr(self, campo, valor.strip().upper())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DNA — {self.nome} ({self.cpf})"

    class Meta:
        verbose_name = "DNA"
        verbose_name_plural = "DNAs"
        ordering = ['-created_at']


class CertidaoRegistro(models.Model):
    """
    Registro de cada Certidão ou Comprovante de Ausência de DNA emitido.

    Permite validar a autenticidade via QR code sem reprocessar o hash —
    o protocolo é gravado no momento da emissão e consultado publicamente.
    """

    class Tipo(models.TextChoices):
        CERTIDAO    = 'CERTIDAO',    'Certidão de Ausência'
        COMPROVANTE = 'COMPROVANTE', 'Comprovante de Consulta'

    protocolo       = models.CharField(max_length=16, unique=True, db_index=True)
    tipo            = models.CharField(max_length=20, choices=Tipo.choices)
    nome_consultado = models.CharField(max_length=255, blank=True)
    cpf_consultado  = models.CharField(max_length=20,  blank=True)
    rg_consultado   = models.CharField(max_length=30,  blank=True)
    emitido_por_nome = models.CharField(max_length=255)
    emitido_em      = models.DateTimeField()

    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='certidoes_emitidas',
    )

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.protocolo}'

    class Meta:
        verbose_name = 'Certidão de Ausência'
        verbose_name_plural = 'Certidões de Ausência'
        ordering = ['-emitido_em']


class FichaVestigioRegistro(models.Model):
    """
    Registro de cada Ficha de Acompanhamento de Vestígio emitida.

    Permite validação pública via QR Code sem autenticação —
    o protocolo é gravado no momento da emissão e consultado externamente.
    """

    protocolo        = models.CharField(max_length=16, unique=True, db_index=True)
    vestigio         = models.ForeignKey(
        Vestigio,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fichas_emitidas',
    )
    vestigio_lacre   = models.CharField(max_length=255, blank=True)
    # Digest SHA-256 do snapshot do vestígio + movimentações no momento da emissão.
    # Permite verificar a integridade do CONTEÚDO impresso (não apenas a emissão):
    # se a ficha for adulterada, o hash recomputado não confere com este registro.
    conteudo_hash    = models.CharField(max_length=64, blank=True, db_index=True)
    emitido_por      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fichas_vestigio_emitidas',
    )
    emitido_por_nome = models.CharField(max_length=255)
    emitido_em       = models.DateTimeField()

    def __str__(self):
        return f'FAV #{self.vestigio_id} — {self.protocolo}'

    class Meta:
        verbose_name = 'Ficha de Acompanhamento Emitida'
        verbose_name_plural = 'Fichas de Acompanhamento Emitidas'
        ordering = ['-emitido_em']
