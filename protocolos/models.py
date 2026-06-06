# protocolos/models.py

import hashlib
from django.db import models
from django.conf import settings
from usuarios.models import AuditModel


class ProtocoloEntrega(AuditModel):

    class TipoEntrega(models.TextChoices):
        MATERIAL        = 'MATERIAL',        'Material Examinado'
        LAUDO           = 'LAUDO',           'Laudo Pericial'
        MATERIAL_E_LAUDO = 'MATERIAL_E_LAUDO', 'Material e Laudo'

    class StatusRecebimento(models.TextChoices):
        PENDENTE                = 'PENDENTE',                'Pendente de Recebimento'
        ASSINADO_ELETRONICAMENTE = 'ASSINADO_ELETRONICAMENTE', 'Assinado Eletronicamente'
        ASSINADO_MANUAL         = 'ASSINADO_MANUAL',         'Assinado Manualmente'

    # ── Número e tipo ──────────────────────────────────────────────────────────
    numero = models.CharField(max_length=20, unique=True, verbose_name='Número')
    tipo_entrega = models.CharField(
        max_length=20, choices=TipoEntrega.choices, default=TipoEntrega.MATERIAL,
        verbose_name='Tipo de Entrega',
    )

    # ── Vestígio (obrigatório) ─────────────────────────────────────────────────
    vestigio = models.ForeignKey(
        'custodia.Vestigio',
        on_delete=models.PROTECT,
        related_name='protocolos',
        verbose_name='Vestígio',
    )
    lacre_na_entrega = models.CharField(
        max_length=255, blank=True,
        verbose_name='Lacre na Entrega',
        help_text='Snapshot do lacre vigente no momento da emissão.',
    )
    descricao_material = models.TextField(verbose_name='Descrição do Material')

    # ── Vinculações ───────────────────────────────────────────────────────────
    # Ocorrência é OBRIGATÓRIA — todo vestígio devolvido deve estar vinculado
    # a uma ocorrência previamente registrada no vestígio (ocorrencias_vinculadas M2M).
    ocorrencia = models.ForeignKey(
        'ocorrencias.Ocorrencia',
        on_delete=models.PROTECT,
        related_name='protocolos_saida',
        verbose_name='Ocorrência',
    )
    procedimento = models.ForeignKey(
        'procedimentos_cadastrados.ProcedimentoCadastrado',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='protocolos',
        verbose_name='Procedimento',
    )

    # ── Destinatário ───────────────────────────────────────────────────────────
    autoridade = models.ForeignKey(
        'autoridades.Autoridade',
        on_delete=models.PROTECT,
        related_name='protocolos',
        verbose_name='Autoridade Demandante',
    )
    unidade_demandante = models.ForeignKey(
        'unidades_demandantes.UnidadeDemandante',
        on_delete=models.PROTECT,
        related_name='protocolos',
        verbose_name='Unidade Demandante',
    )

    # ── Entregador (snapshot imutável do usuário logado) ───────────────────────
    entregue_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='protocolos_emitidos',
        verbose_name='Entregue Por (FK)',
    )
    entregue_por_nome = models.CharField(max_length=255, verbose_name='Nome do Entregador')
    entregue_por_cargo = models.CharField(max_length=100, verbose_name='Cargo do Entregador')
    entregue_por_cpf = models.CharField(max_length=14, verbose_name='CPF do Entregador')
    entregue_em = models.DateTimeField(verbose_name='Data/Hora da Entrega')

    # ── Recebedor (texto livre + FK opcional) ──────────────────────────────────
    recebido_por_nome = models.CharField(max_length=255, verbose_name='Nome do Recebedor')
    recebido_por_cargo = models.CharField(max_length=100, verbose_name='Cargo do Recebedor')
    recebido_por_cpf = models.CharField(max_length=14, blank=True, verbose_name='CPF do Recebedor')
    recebido_por_matricula = models.CharField(max_length=50, blank=True, verbose_name='Matrícula do Recebedor')
    recebido_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='protocolos_recebidos',
        verbose_name='Recebedor (usuário do sistema)',
    )
    recebido_em = models.DateTimeField(null=True, blank=True, verbose_name='Data/Hora do Recebimento')

    # ── Status ────────────────────────────────────────────────────────────────
    status_recebimento = models.CharField(
        max_length=30,
        choices=StatusRecebimento.choices,
        default=StatusRecebimento.PENDENTE,
        verbose_name='Status do Recebimento',
    )

    # ── Autenticidade ─────────────────────────────────────────────────────────
    protocolo_hash = models.CharField(
        max_length=32, unique=True,
        verbose_name='Hash de Autenticidade',
    )

    # ── Rastreio de finalização automática ────────────────────────────────────
    vestigio_foi_finalizado = models.BooleanField(
        default=False,
        verbose_name='Vestígio Finalizado pelo Protocolo',
        help_text='True quando este protocolo acionou a finalização automática do vestígio.',
    )

    observacoes = models.TextField(blank=True, verbose_name='Observações')

    class Meta:
        verbose_name = 'Protocolo de Entrega'
        verbose_name_plural = 'Protocolos de Entrega'
        ordering = ['-created_at']

    def __str__(self):
        return f'Protocolo {self.numero} — {self.vestigio}'

    @staticmethod
    def gerar_hash(numero: str, vestigio_id: int) -> str:
        raw = f'protocolo-{numero}-vest{vestigio_id}-spr'
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
        return f'{digest[:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}'
