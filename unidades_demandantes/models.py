from django.db import models
from django.core.exceptions import ValidationError
from usuarios.models import AuditModel
import unicodedata


class UnidadeDemandante(AuditModel):
    sigla = models.CharField(max_length=20, unique=True, help_text="Sigla da unidade demandante (ex: CF, 1ºDP, DEAM).")
    nome = models.CharField(max_length=255, unique=True, help_text="Nome por extenso da unidade demandante.")

    def save(self, *args, **kwargs):
        self.sigla = self.sigla.upper()
        self.nome = self.nome.upper()
        super(UnidadeDemandante, self).save(*args, **kwargs)

    def clean(self):
        """Valida se já existe sigla ou nome similar (sem considerar acentos)"""
        super().clean()
        
        # Normaliza para comparação
        sigla_normalizada = self.remover_acentos(self.sigla.upper())
        nome_normalizado = self.remover_acentos(self.nome.upper())
        
        # Busca outras unidades (excluindo a atual se estiver editando)
        outras = UnidadeDemandante.objects.exclude(pk=self.pk)
        
        for outra in outras:
            # Valida sigla
            if self.remover_acentos(outra.sigla.upper()) == sigla_normalizada:
                raise ValidationError({
                    'sigla': f'Já existe uma unidade com sigla similar: "{outra.sigla}"'
                })
            
            # Valida nome
            if self.remover_acentos(outra.nome.upper()) == nome_normalizado:
                raise ValidationError({
                    'nome': f'Já existe uma unidade com nome similar: "{outra.nome}"'
                })
    
    @staticmethod
    def remover_acentos(texto):
        """Remove acentos de uma string para comparação"""
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join([c for c in nfkd if not unicodedata.combining(c)])

    def __str__(self):
        return f"{self.sigla} - {self.nome}"

    class Meta:
        verbose_name = "Unidade Demandante"
        verbose_name_plural = "Unidades Demandantes"
        ordering = ['sigla']