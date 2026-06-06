from django.contrib import admin
from .models import ProtocoloEntrega


@admin.register(ProtocoloEntrega)
class ProtocoloEntregaAdmin(admin.ModelAdmin):
    list_display = ['numero', 'vestigio', 'tipo_entrega', 'status_recebimento', 'entregue_por_nome', 'entregue_em']
    list_filter = ['tipo_entrega', 'status_recebimento']
    search_fields = ['numero', 'vestigio__lacre', 'recebido_por_nome', 'entregue_por_nome']
    readonly_fields = ['numero', 'protocolo_hash', 'entregue_em', 'entregue_por_nome', 'entregue_por_cpf', 'entregue_por_cargo']
