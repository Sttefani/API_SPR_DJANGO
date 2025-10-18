from django.db import models


class LaudoReferencia(models.Model):
    """PDFs de laudos antigos para usar como referência"""
    titulo = models.CharField(max_length=200)
    tipo_exame = models.CharField(max_length=100)
    arquivo_pdf = models.FileField(upload_to='laudos_referencia/')
    texto_extraido = models.TextField(blank=True)
    processado = models.BooleanField(default=False)
    pasta_origem = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Laudo de Referência"
        verbose_name_plural = "Laudos de Referência"
    
    def __str__(self):
        return f"{self.titulo} ({self.tipo_exame})"