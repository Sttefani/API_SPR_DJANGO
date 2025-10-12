# ocorrencias/endereco_models.py

from django.db import models
from django.conf import settings
from usuarios.models import AuditModel


class TipoOcorrencia(models.TextChoices):
    """Tipo de ocorrência: Interna (laboratório) ou Externa (cena)"""
    INTERNA = 'INTERNA', 'Interna (Laboratório)'
    EXTERNA = 'EXTERNA', 'Externa (Cena de Crime)'


class EnderecoOcorrencia(AuditModel):
    """
    Módulo separado para endereços de ocorrências.
    Não mexe no model Ocorrencia existente (segurança).
    """
    
    # Relação 1:1 com Ocorrência
    ocorrencia = models.OneToOneField(
        'Ocorrencia',
        on_delete=models.CASCADE,
        related_name='endereco',
        verbose_name='Ocorrência'
    )
    
    tipo = models.CharField(
        max_length=10,
        choices=TipoOcorrencia.choices,
        default=TipoOcorrencia.EXTERNA,
        verbose_name='Tipo de Ocorrência'
    )
    
    # Campos de endereço
    logradouro = models.CharField(max_length=255, blank=True, verbose_name='Logradouro')
    numero = models.CharField(max_length=20, blank=True, verbose_name='Número')
    complemento = models.CharField(max_length=100, blank=True, verbose_name='Complemento')
    bairro = models.CharField(max_length=100, blank=True, verbose_name='Bairro')
    cep = models.CharField(max_length=10, blank=True, verbose_name='CEP')
    
    # Geolocalização (para BI futuro)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Latitude')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Longitude')
    
    ponto_referencia = models.CharField(max_length=255, blank=True, verbose_name='Ponto de Referência')
    
    @property
    def endereco_completo(self):
        """Retorna endereço formatado"""
        partes = []
        if self.logradouro:
            partes.append(self.logradouro)
        if self.numero:
            partes.append(f"nº {self.numero}")
        if self.complemento:
            partes.append(self.complemento)
        if self.bairro:
            partes.append(f"Bairro: {self.bairro}")
        if self.cep:
            partes.append(f"CEP: {self.cep}")
        return ", ".join(partes) if partes else "Endereço não informado"
    
    @property
    def tem_coordenadas(self):
        return self.latitude is not None and self.longitude is not None
    
    def __str__(self):
        if self.tipo == TipoOcorrencia.INTERNA:
            return f"Endereço (Interna) - {self.ocorrencia.numero_ocorrencia}"
        return f"Endereço (Externa) - {self.endereco_completo[:50]}"
    
    class Meta:
        verbose_name = "Endereço de Ocorrência"
        verbose_name_plural = "Endereços de Ocorrências"
        ordering = ['-created_at']