# ordens_servico/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from ocorrencias.models import Ocorrencia
from usuarios.models import AuditModel
from unidades_demandantes.models import UnidadeDemandante
from autoridades.models import Autoridade
from procedimentos_cadastrados.models import ProcedimentoCadastrado
from tipos_documento.models import TipoDocumento

class OrdemServico(AuditModel):
    """
    Representa uma Ordem de Serviço, um documento formal com dados
    espelhados da ocorrência e seus próprios campos.
    """
    class Status(models.TextChoices):
        AGUARDANDO_CIENCIA = 'AGUARDANDO_CIENCIA', 'Aguardando Ciência'
        ABERTA = 'ABERTA', 'Aberta'
        VENCIDA = 'VENCIDA', 'Vencida'
        CONCLUIDA = 'CONCLUIDA', 'Concluída'

    # --- Relação Principal ---
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name='ordens_servico')
    
    # --- Dados da Própria OS ---
    numero_os = models.CharField(max_length=20, unique=True, editable=False)
    prazo_dias = models.PositiveIntegerField(verbose_name="Prazo para Conclusão (em dias)")
    texto_padrao = models.TextField(editable=False, default="O DIRETOR, NO USO DE SUAS ATRIBUIÇÕES LEGAIS, EMITE A PRESENTE ORDEM DE SERVIÇO, DETERMINANDO A REALIZAÇÃO DOS EXAMES E CONFECÇÃO DO LAUDO PERICIAL.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AGUARDANDO_CIENCIA)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    
    # --- DADOS ESPELHADOS DA OCORRÊNCIA (Snapshot no momento da criação) ---
    # Esses campos são preenchidos uma vez e não mudam, mesmo que a ocorrência mude.
    unidade_demandante = models.ForeignKey(UnidadeDemandante, on_delete=models.PROTECT, null=True)
    autoridade_demandante = models.ForeignKey(Autoridade, on_delete=models.PROTECT, null=True)
    procedimento = models.ForeignKey(ProcedimentoCadastrado, on_delete=models.PROTECT, null=True, blank=True)
    
    # --- NOVOS CAMPOS ESPECÍFICOS DA OS (Preenchidos pelo usuário) ---
    tipo_documento_referencia = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Documento de Referência")
    numero_documento_referencia = models.CharField(max_length=50, blank=True, verbose_name="Nº do Documento de Referência")
    processo_sei_referencia = models.CharField(max_length=50, blank=True, verbose_name="Processo SEI de Referência")
    processo_judicial_referencia = models.CharField(max_length=50, blank=True, verbose_name="Processo Judicial de Referência")

    # --- DADOS DE CIÊNCIA (Assinatura do Perito) ---
    ciente_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='os_cientes', verbose_name="Perito Ciente"
    )
    data_ciencia = models.DateTimeField(null=True, blank=True)
    ip_ciencia = models.GenericIPAddressField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Gera o número da OS na primeira criação
        if not self.pk:
            ano = timezone.now().year
            ultimo_os = OrdemServico.objects.filter(numero_os__endswith=f"/{ano}").order_by('id').last()
            novo_numero = (int(ultimo_os.numero_os.split('/')[0]) + 1) if ultimo_os else 1
            self.numero_os = f"{novo_numero:04d}/{ano}"

        super(OrdemServico, self).save(*args, **kwargs)

    def __str__(self):
        return f"OS {self.numero_os}"

    class Meta:
        verbose_name = "Ordem de Serviço"
        ordering = ['-created_at']