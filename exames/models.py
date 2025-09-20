# exames/models.py

from django.db import models
from usuarios.models import AuditModel
from servicos_periciais.models import ServicoPericial  # Importa a "categoria"


class Exame(AuditModel):
    codigo = models.CharField(max_length=20, unique=True, help_text="Código do exame (ex: 1.0.0.1).")
    nome = models.CharField(max_length=255, unique=True, help_text="Nome do exame.")

    servico_pericial = models.ForeignKey(
        ServicoPericial,
        on_delete=models.PROTECT,
        related_name='exames',
        verbose_name='Serviço Pericial Responsável'
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sub_exames',
        verbose_name='Exame Pai (Grupo)'
    )

    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super(Exame, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = "Exame"
        verbose_name_plural = "Exames"
        ordering = ['servico_pericial', 'codigo']