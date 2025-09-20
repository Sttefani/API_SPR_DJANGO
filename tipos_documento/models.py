# tipos_documento/models.py

from django.db import models
from usuarios.models import AuditModel


class TipoDocumento(AuditModel):
    nome = models.CharField(max_length=100, unique=True,
                            help_text="Nome do tipo de documento (ex: REQUISIÇÃO, OFÍCIO).")

    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super(TipoDocumento, self).save(*args, **kwargs)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documentos"
        ordering = ['nome']