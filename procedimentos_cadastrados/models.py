# procedimentos_cadastrados/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import datetime
from usuarios.models import AuditModel
from procedimentos.models import Procedimento


def ano_atual():
    return datetime.date.today().year


class ProcedimentoCadastrado(AuditModel):
    tipo_procedimento = models.ForeignKey(
        Procedimento,
        on_delete=models.PROTECT,
        related_name='cadastros',
        verbose_name='Tipo de Procedimento'
    )

    # MUDANÇA PRINCIPAL AQUI
    numero = models.CharField(
        max_length=50,
        help_text="Número do procedimento (pode conter letras e caracteres especiais)."
    )

    ano = models.PositiveIntegerField(
        help_text="Ano do procedimento.",
        validators=[MinValueValidator(1900), MaxValueValidator(ano_atual() + 1)],
        default=ano_atual
    )

    # A regra de caixa alta continua valendo para o número
    def save(self, *args, **kwargs):
        self.numero = self.numero.upper()
        super(ProcedimentoCadastrado, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.tipo_procedimento.sigla} - {self.numero}/{self.ano}"

    class Meta:
        verbose_name = "Procedimento Cadastrado"
        verbose_name_plural = "Procedimentos Cadastrados"
        ordering = ['-ano', '-numero']
        constraints = [
            models.UniqueConstraint(fields=['tipo_procedimento', 'numero', 'ano'],
                                    name='unique_procedimento_cadastrado')
        ]