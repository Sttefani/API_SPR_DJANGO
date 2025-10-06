# classificacoes/models.py

from django.db import models
from usuarios.models import AuditModel
from servicos_periciais.models import ServicoPericial # <-- 1. IMPORTA O MODELO NECESSÁRIO

class ClassificacaoOcorrencia(AuditModel):
    codigo = models.CharField(max_length=20, unique=True, help_text="Código da classificação (ex: 1.0.1).")
    nome = models.CharField(max_length=255, unique=True,
                            help_text="Nome da classificação (ex: ACIDENTE DE TRÂNSITO COM VÍTIMA FATAL).")

    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='subgrupos',
        verbose_name='Grupo Pai'
    )

    # --- INÍCIO DA NOVA SEÇÃO ---
    servicos_periciais = models.ManyToManyField(
        ServicoPericial,
        blank=True, # Permite que uma classificação não esteja associada a nenhum serviço.
        verbose_name="Serviços Periciais Associados",
        help_text="Selecione os serviços periciais aos quais esta classificação se aplica. Se for um Grupo Principal, os subgrupos herdarão estas associações."
    )
    # --- FIM DA NOVA SEÇÃO ---

    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super(ClassificacaoOcorrencia, self).save(*args, **kwargs)

    def __str__(self):
        if self.parent:
            return f"{self.codigo} - {self.nome} (Subgrupo de: {self.parent.nome})"
        return f"{self.codigo} - {self.nome} (Grupo Principal)"

    class Meta:
        verbose_name = "Classificação de Ocorrência"
        verbose_name_plural = "Classificações de Ocorrências"
        ordering = ['codigo']