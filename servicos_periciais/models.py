# servicos_periciais/models.py

from django.db import models
from usuarios.models import AuditModel

class ServicoPericial(AuditModel):
    sigla = models.CharField(max_length=10, unique=True, help_text="Sigla do serviço com no máximo 10 caracteres.")
    nome = models.CharField(max_length=50, unique=True, help_text="Nome completo do serviço pericial.")

    def save(self, *args, **kwargs):
        # Garante que sigla e nome sejam sempre salvos em caixa alta.
        self.sigla = self.sigla.upper()
        self.nome = self.nome.upper() # Adicionamos esta linha
        super(ServicoPericial, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.sigla} - {self.nome}"

    class Meta:
        verbose_name = "Serviço Pericial"
        verbose_name_plural = "Serviços Periciais"
        # A constraint foi removida.