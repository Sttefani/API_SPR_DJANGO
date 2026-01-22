# movimentacoes/models.py

from django.db import models
from ocorrencias.models import Ocorrencia
from usuarios.models import AuditModel


class Movimentacao(AuditModel):
    """
    Registra um evento ou "movimentação" no histórico de uma ocorrência.
    Funciona como um log auditável com lixeira.
    """

    # Relação com a Ocorrência pai
    ocorrencia = models.ForeignKey(
        Ocorrencia,
        on_delete=models.CASCADE,
        related_name="movimentacoes",
        verbose_name="Ocorrência",
    )

    # Campo para o 'Assunto'
    assunto = models.CharField(max_length=255, verbose_name="Assunto da Movimentação")

    # Campo para a 'Descrição'
    descricao = models.TextField(verbose_name="Descrição Detalhada")

    ip_registro = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="Endereço de IP do Registro"
    )

    # ========== NOVO CAMPO ==========
    visualizado_admin = models.BooleanField(
        default=False, verbose_name="Visualizado pelo Administrativo"
    )
    # ================================

    def __str__(self):
        data_formatada = self.created_at.strftime("%d/%m/%Y %H:%M")
        return f"({data_formatada}) {self.assunto}"

    class Meta:
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"
        ordering = ["created_at"]
