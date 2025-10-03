from django.db import models
from django.core.exceptions import ValidationError
from usuarios.models import AuditModel
from cargos.models import Cargo
import unicodedata


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

    def clean(self):
        """Valida se já existe nome similar (sem considerar acentos)"""
        super().clean()
        
        # Normaliza apenas para comparação
        nome_normalizado = self.remover_acentos(self.nome.upper())
        
        # Busca outras autoridades (excluindo a atual se estiver editando)
        outras = Autoridade.objects.exclude(pk=self.pk)
        
        for outra in outras:
            if self.remover_acentos(outra.nome.upper()) == nome_normalizado:
                raise ValidationError({
                    'nome': f'Já existe uma autoridade cadastrada com nome similar: "{outra.nome}"'
                })
    
    @staticmethod
    def remover_acentos(texto):
        """Remove acentos de uma string para comparação"""
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join([c for c in nfkd if not unicodedata.combining(c)])

    def __str__(self):
        return f"{self.nome} ({self.cargo.nome})"

    class Meta:
        verbose_name = "Autoridade"
        verbose_name_plural = "Autoridades"
        ordering = ['nome']