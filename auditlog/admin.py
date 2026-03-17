"""
# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025
"""

from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'usuario', 'acao', 'modelo', 'objeto_repr')
    list_filter = ('acao', 'app_label', 'modelo')
    search_fields = ('usuario__username', 'objeto_repr', 'modelo')
    readonly_fields = ('usuario', 'acao', 'app_label', 'modelo', 'objeto_id', 'objeto_repr', 'timestamp')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
