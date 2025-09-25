# fichas/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from ocorrencias.models import Ocorrencia
from usuarios.models import AuditModel

# =============================================================================
# FICHA PARA LOCAL DE CRIME (GENÉRICO, SPA)
# =============================================================================
class FichaLocalCrime(AuditModel):
    ocorrencia = models.OneToOneField(Ocorrencia, on_delete=models.CASCADE, primary_key=True, related_name='ficha_local_crime')
    endereco_completo = models.CharField(max_length=400, blank=True, verbose_name="Endereço Completo")
    coordenadas = models.CharField(max_length=50, blank=True, verbose_name="Coordenadas GPS")
    local_fechado = models.BooleanField(default=False, verbose_name="Local Fechado")
    endereco_nao_localizado = models.BooleanField(default=False, verbose_name="Endereço Não Localizado")
    local_preservado = models.BooleanField(default=True, verbose_name="Local Preservado")
    auxiliar = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'perfil': 'OPERACIONAL'},
        related_name='fichas_como_auxiliar',
        verbose_name="Auxiliar Operacional"
    )
    observacoes_local = models.TextField(blank=True, verbose_name="Observações Gerais do Local")
    condicoes_climaticas = models.CharField(max_length=100, blank=True, verbose_name="Condições Climáticas")
    iluminacao = models.CharField(
        max_length=50,
        choices=[('NATURAL', 'Luz Natural'), ('ARTIFICIAL', 'Luz Artificial'), ('MISTA', 'Mista'), ('INSUFICIENTE', 'Insuficiente')],
        blank=True, verbose_name="Condições de Iluminação"
    )
    def __str__(self):
        return f"Ficha Local de Crime - {self.ocorrencia.numero_ocorrencia}"
    class Meta:
        verbose_name = "Ficha de Local de Crime"


# =============================================================================
# FICHA PARA ACIDENTE DE TRÂNSITO (PLANTÃO / SIV)
# =============================================================================
class FichaAcidenteTransito(AuditModel):
    ocorrencia = models.OneToOneField(Ocorrencia, on_delete=models.CASCADE, primary_key=True, related_name='ficha_acidente_transito')
    endereco_completo = models.CharField(max_length=400, verbose_name="Endereço Completo", blank=True)
    coordenadas = models.CharField(max_length=50, blank=True, verbose_name="Coordenadas GPS")
    is_endereco_nao_localizado = models.BooleanField(default=False, verbose_name="Endereço Não Localizado?")
    is_veiculo_oficial = models.BooleanField(default=False, verbose_name="Veículo Oficial Envolvido?")
    orgao_veiculo_oficial = models.CharField(max_length=100, blank=True, verbose_name="Órgão Vinculado ao Veículo")
    auxiliar = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fichas_acidente_como_auxiliar',
        verbose_name="Auxiliar Operacional",
        limit_choices_to={'perfil': 'OPERACIONAL'}
    )
    
    class Meta:
        verbose_name = "Ficha de Acidente de Trânsito"


# =============================================================================
# FICHA PARA CONSTATAÇÃO EM SUBSTÂNCIA (PRELIMINAR)
# =============================================================================
class FichaConstatacaoSubstancia(AuditModel):
    ocorrencia = models.OneToOneField(Ocorrencia, on_delete=models.CASCADE, primary_key=True, related_name='ficha_constatacao_substancia')
    material_encontrado_em_poder_de = models.CharField(max_length=255, blank=True)
    class Meta:
        verbose_name = "Ficha de Constatação em Substância"


# =============================================================================
# FICHA PARA DOCUMENTOSCOPIA e SPMD
# =============================================================================
class FichaDocumentoscopia(AuditModel):
    ocorrencia = models.OneToOneField(Ocorrencia, on_delete=models.CASCADE, primary_key=True, related_name='ficha_documentoscopia')
    material_encontrado_em_poder_de = models.CharField(max_length=255, blank=True)
    class Meta:
        verbose_name = "Ficha de Documentoscopia / SPMD"


# =============================================================================
# FICHA PARA BALÍSTICA, LAB. QUÍMICA, SEPAEL, LGF/LBF
# =============================================================================
class FichaMaterialDiverso(AuditModel):
    ocorrencia = models.OneToOneField(Ocorrencia, on_delete=models.CASCADE, primary_key=True, related_name='ficha_material_diverso')
    lacre_recebimento = models.CharField(max_length=100, blank=True)
    descricao = models.CharField(max_length=255, blank=True, verbose_name="Descrição (Específica)")
    material_encontrado_em_poder_de = models.CharField(max_length=255, blank=True)
    nome_doador_local_vestigio = models.CharField(max_length=255, blank=True, verbose_name="Nome do Doador / Local do Vestígio (LGF/LBF)")
    class Meta:
        verbose_name = "Ficha de Material, Objeto, Vestígios (Balística, etc.)"


# =============================================================================
# SUB-MODELOS DINÂMICOS
# =============================================================================
class Vitima(AuditModel):
    ficha_local_crime = models.ForeignKey(FichaLocalCrime, on_delete=models.CASCADE, related_name='vitimas', null=True, blank=True)
    ficha_acidente = models.ForeignKey(FichaAcidenteTransito, on_delete=models.CASCADE, related_name='vitimas', null=True, blank=True)
    nome = models.CharField(max_length=200, verbose_name="Nome da Vítima")
    class Meta:
        verbose_name = "Vítima"

class Vestigio(AuditModel):
    ficha_local_crime = models.ForeignKey(FichaLocalCrime, on_delete=models.CASCADE, related_name='vestigios')
    item_numero = models.PositiveIntegerField(verbose_name="Item Nº")
    descricao = models.TextField(verbose_name="Descrição Detalhada do Vestígio")
    class Meta:
        verbose_name = "Vestígio Coletado"
        unique_together = ('ficha_local_crime', 'item_numero')
        ordering = ['item_numero']

class Veiculo(AuditModel):
    ficha_acidente = models.ForeignKey(FichaAcidenteTransito, on_delete=models.CASCADE, related_name='veiculos', null=True, blank=True)
    ficha_identificacao = models.ForeignKey('FichaIdentificacaoVeicular', on_delete=models.CASCADE, related_name='veiculos', null=True, blank=True)
    placa = models.CharField(max_length=10, blank=True)
    chassi = models.CharField(max_length=40, blank=True)
    motor = models.CharField(max_length=40, blank=True)
    cambio = models.CharField(max_length=40, blank=True)
    renavam = models.CharField(max_length=20, blank=True)
    ano_modelo = models.CharField(max_length=10, blank=True)
    cor = models.CharField(max_length=30, blank=True)
    marca = models.CharField(max_length=50, blank=True)
    modelo = models.CharField(max_length=50, blank=True)
    def save(self, *args, **kwargs):
        self.placa = self.placa.upper()
        self.chassi = self.chassi.upper()
        self.motor = self.motor.upper()
        self.cambio = self.cambio.upper()
        super(Veiculo, self).save(*args, **kwargs)
    class Meta:
        verbose_name = "Veículo"

class FichaIdentificacaoVeicular(AuditModel):
    ocorrencia = models.OneToOneField(Ocorrencia, on_delete=models.CASCADE, primary_key=True, related_name='ficha_identificacao_veicular')
    endereco_completo = models.CharField(max_length=400, blank=True, verbose_name="Local de Encontro do Veículo")
    class Meta:
        verbose_name = "Ficha de Identificação Veicular"

class ItemSubstancia(AuditModel):
    ficha = models.ForeignKey(FichaConstatacaoSubstancia, on_delete=models.CASCADE, related_name='itens_substancia')
    substancia = models.CharField(max_length=100)
    quantidade = models.CharField(max_length=50)
    massa_bruta = models.DecimalField(max_digits=10, decimal_places=3)
    massa_retirada_exame = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    massa_retirada_contraprova = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    massa_liquida_devolvida = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    class Meta:
        verbose_name = "Item de Substância"

class ItemDocumentoscopia(AuditModel):
    ficha = models.ForeignKey(FichaDocumentoscopia, on_delete=models.CASCADE, related_name='itens_documentoscopia')
    descricao_material = models.TextField()
    lacre_recebimento = models.CharField(max_length=100, blank=True)
    class Meta:
        verbose_name = "Item de Documentoscopia"

class ItemMaterial(AuditModel):
    ficha = models.ForeignKey(FichaMaterialDiverso, on_delete=models.CASCADE, related_name='itens_material')
    material = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    quantidade = models.CharField(max_length=50)
    class Meta:
        verbose_name = "Item de Material"

class Lacre(AuditModel):
    class TipoLacre(models.TextChoices):
        RECEBIMENTO = 'RECEBIMENTO', 'Recebimento'
        DEFINITIVO = 'DEFINITIVO', 'Definitivo'
        DEVOLUCAO = 'DEVOLUCAO', 'Devolução'
        CONTRAPROVA = 'CONTRAPROVA', 'Contraprova'
        TRANSPORTE = 'TRANSPORTE', 'Transporte'
        TEMPORARIO = 'TEMPORARIO', 'Temporário'
    numero = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TipoLacre.choices)
    vestigio = models.ForeignKey(Vestigio, on_delete=models.CASCADE, related_name='lacres', null=True, blank=True)
    item_substancia = models.ForeignKey(ItemSubstancia, on_delete=models.CASCADE, related_name='lacres', null=True, blank=True)
    class Meta:
        verbose_name = "Lacre"