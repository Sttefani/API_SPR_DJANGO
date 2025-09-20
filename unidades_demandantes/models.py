# unidades_demandantes/models.py

from django.db import models
from usuarios.models import AuditModel

class UnidadeDemandante(AuditModel):
    sigla = models.CharField(max_length=20, unique=True, help_text="Sigla da unidade demandante (ex: CF, 1ºDP, DEAM).")
    nome = models.CharField(max_length=255, unique=True, help_text="Nome por extenso da unidade demandante.")

    def save(self, *args, **kwargs):
        # Garante que sigla e nome sejam sempre salvos em caixa alta.
        self.sigla = self.sigla.upper()
        self.nome = self.nome.upper()
        super(UnidadeDemandante, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.sigla} - {self.nome}"

    class Meta:
        verbose_name = "Unidade Demandante"
        verbose_name_plural = "Unidades Demandantes"
        ordering = ['sigla']