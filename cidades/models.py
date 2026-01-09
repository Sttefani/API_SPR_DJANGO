from django.db import models
from usuarios.models import AuditModel


class Cidade(AuditModel):
    nome = models.CharField(max_length=100, unique=True, help_text="Nome da cidade.")

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super(Cidade, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        ordering = ["nome"]


class Bairro(AuditModel):
    """
    Modelo de Bairro vinculado a uma Cidade.
    Garante padronização dos nomes de bairros para relatórios estatísticos.
    """

    nome = models.CharField(max_length=100, verbose_name="Nome do Bairro")
    cidade = models.ForeignKey(
        Cidade, on_delete=models.PROTECT, related_name="bairros", verbose_name="Cidade"
    )

    def __str__(self):
        return f"{self.nome} - {self.cidade.nome}"

    def save(self, *args, **kwargs):
        # Normaliza o nome: MAIÚSCULO e sem espaços extras
        self.nome = " ".join(self.nome.upper().split())
        super(Bairro, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Bairro"
        verbose_name_plural = "Bairros"
        ordering = ["cidade__nome", "nome"]
        # Garante que não existe bairro duplicado na mesma cidade
        constraints = [
            models.UniqueConstraint(
                fields=["nome", "cidade"], name="unique_bairro_por_cidade"
            )
        ]
