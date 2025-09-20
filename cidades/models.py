from django.db import models
from usuarios.models import AuditModel # Reutilizando nosso modelo base de auditoria

class Cidade(AuditModel):
    nome = models.CharField(max_length=100, unique=True, help_text="Nome da cidade.")


    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super(Cidade, self).save(*args, **kwargs)


    class Meta:
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        ordering = ['nome'] # Ordena as cidades por nome em ordem alfabética
# Create your models here.
