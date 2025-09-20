from django.db import models
from usuarios.models import AuditModel
from cargos.models import Cargo  # <-- Importa o modelo do outro app


class Autoridade(AuditModel):
    nome = models.CharField(max_length=255, unique=True, help_text="Nome completo da autoridade.")

    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        related_name='autoridades',
        help_text="Cargo ocupado pela autoridade."
    )

    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super(Autoridade, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} ({self.cargo.nome})"

    class Meta:
        verbose_name = "Autoridade"
        verbose_name_plural = "Autoridades"
        ordering = ['nome']