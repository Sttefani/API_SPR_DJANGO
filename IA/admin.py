from django.contrib import admin
from .models import LaudoReferencia

@admin.register(LaudoReferencia)
class LaudoReferenciaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo_exame', 'processado', 'created_at']
    list_filter = ['tipo_exame', 'processado']
    search_fields = ['titulo', 'tipo_exame']