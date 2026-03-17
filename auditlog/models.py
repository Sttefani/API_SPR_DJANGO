"""
# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025
"""

from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    class Acao(models.TextChoices):
        CRIOU = 'criou', 'Criou'
        EDITOU = 'editou', 'Editou'
        DELETOU = 'deletou', 'Deletou'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Usuário',
        related_name='audit_logs',
    )
    acao = models.CharField(
        max_length=10,
        choices=Acao.choices,
        verbose_name='Ação',
    )
    app_label = models.CharField(max_length=50, verbose_name='Módulo (interno)')
    modelo = models.CharField(max_length=100, verbose_name='Entidade')
    objeto_id = models.CharField(max_length=100, verbose_name='ID do Objeto')
    objeto_repr = models.CharField(max_length=250, verbose_name='Descrição do Objeto')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Data/Hora')

    class Meta:
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-timestamp']

    def __str__(self):
        usuario = self.usuario.get_full_name() or self.usuario.username if self.usuario else 'Sistema'
        return f"{usuario} {self.acao} {self.modelo} #{self.objeto_id}"
