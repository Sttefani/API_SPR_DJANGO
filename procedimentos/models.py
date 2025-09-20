# procedimentos/models.py

from django.db import models
from usuarios.models import AuditModel

class Procedimento(AuditModel):
    sigla = models.CharField(max_length=20, unique=True, help_text="Sigla do tipo de procedimento (ex: APF, IP, BO).")
    nome = models.CharField(max_length=255, unique=True, help_text="Nome por extenso do tipo de procedimento.")

    def save(self, *args, **kwargs):
        self.sigla = self.sigla.upper()
        self.nome = self.nome.upper()
        super(Procedimento, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.sigla} - {self.nome}"

    class Meta:
        verbose_name = "Tipo de Procedimento"
        verbose_name_plural = "Tipos de Procedimentos"
        ordering = ['sigla']