# tipos_documento/models.py

import unicodedata
from django.db import models
from usuarios.models import AuditModel


class TipoDocumento(AuditModel):
    nome = models.CharField(max_length=100, unique=True,
                            help_text="Nome do tipo de documento (ex: REQUISIÇÃO, OFÍCIO).")

    def save(self, *args, **kwargs):
        # Normaliza: remove acentos + uppercase
        self.nome = self.remover_acentos(self.nome.upper())
        super(TipoDocumento, self).save(*args, **kwargs)
    
    @staticmethod
    def remover_acentos(texto):
        """Remove acentos de uma string"""
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join([c for c in nfkd if not unicodedata.combining(c)])

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documentos"
        ordering = ['nome']