# classificacoes/models.py

from django.db import models
from usuarios.models import AuditModel


class ClassificacaoOcorrencia(AuditModel):
    codigo = models.CharField(max_length=20, unique=True, help_text="Código da classificação (ex: 1.0.1).")
    nome = models.CharField(max_length=255, unique=True,
                            help_text="Nome da classificação (ex: ACIDENTE DE TRÂNSITO COM VÍTIMA FATAL).")

    # O campo 'parent' que cria a relação de hierarquia (pai/filho)
    parent = models.ForeignKey(
        'self',  # Aponta para o próprio modelo
        on_delete=models.PROTECT,  # Impede a exclusão de um pai se ele tiver filhos
        null=True,  # Permite que um item não tenha pai (um grupo principal)
        blank=True,
        related_name='subgrupos',
        verbose_name='Grupo Pai'
    )

    def save(self, *args, **kwargs):
        # Padroniza para caixa alta
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