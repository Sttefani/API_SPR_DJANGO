from django.db import models
from usuarios.models import AuditModel

# cargos/models.py
class Cargo(AuditModel):
    nome = models.CharField(max_length=100, unique=True, help_text="Nome do cargo (ex: Delegado de Polícia, Juiz de Direito).")

    # ADICIONE ESTE MÉTODO
    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super(Cargo, self).save(*args, **kwargs)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        ordering = ['nome']