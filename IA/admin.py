from django.contrib import admin
from .models import LaudoReferencia, TemplateLaudo, LaudoGerado

@admin.register(LaudoReferencia)
class LaudoReferenciaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo_exame', 'processado', 'created_at']
    list_filter = ['processado', 'tipo_exame', 'created_at']
    search_fields = ['titulo', 'tipo_exame', 'texto_extraido']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'tipo_exame', 'arquivo_pdf')
        }),
        ('Processamento', {
            'fields': ('texto_extraido', 'processado', 'pasta_origem')
        }),
        ('Metadados', {
            'fields': ('created_at',)
        }),
    )


@admin.register(TemplateLaudo)
class TemplateLaudoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo', 'ativo', 'atualizado_em']
    list_filter = ['tipo', 'ativo', 'criado_em']
    search_fields = ['nome', 'descricao', 'tipo']
    readonly_fields = ['criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('tipo', 'nome', 'descricao', 'ativo')
        }),
        ('Template', {
            'fields': ('template_texto',),
            'description': 'Use {{variavel}} para criar placeholders. Ex: {{nome_perito}}, {{resultado}}'
        }),
        ('Configuração de Campos', {
            'fields': ('campos_obrigatorios', 'campos_com_validacao', 'campos_automaticos'),
            'classes': ('collapse',)
        }),
        ('Exemplo de Preenchimento', {
            'fields': ('exemplo_dados',),
            'classes': ('collapse',),
            'description': 'JSON com exemplo de como preencher o template'
        }),
        ('Metadados', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['testar_preenchimento', 'duplicar_template']
    
    def testar_preenchimento(self, request, queryset):
        """Testa o preenchimento do template com dados de exemplo"""
        for template in queryset:
            try:
                laudo = template.preencher(template.exemplo_dados)
                self.message_user(request, f'✅ Template "{template.nome}" preenchido com sucesso!')
            except Exception as e:
                self.message_user(request, f'❌ Erro no template "{template.nome}": {str(e)}', level='ERROR')
    
    testar_preenchimento.short_description = '🧪 Testar preenchimento com dados de exemplo'
    
    def duplicar_template(self, request, queryset):
        """Duplica templates selecionados"""
        for template in queryset:
            template.pk = None
            template.tipo = f"{template.tipo}_copia"
            template.nome = f"{template.nome} (Cópia)"
            template.save()
            self.message_user(request, f'✅ Template "{template.nome}" duplicado!')
    
    duplicar_template.short_description = '📋 Duplicar templates'


@admin.register(LaudoGerado)
class LaudoGeradoAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'template', 'resultado', 'gerado_por', 'gerado_em']
    list_filter = ['template__tipo', 'resultado','gerado_em']
    search_fields = ['laudo_texto', 'gerado_por', 'resultado']
    readonly_fields = ['gerado_em']
    date_hierarchy = 'gerado_em'
    
    fieldsets = (
        ('Informações do Laudo', {
            'fields': ('template', 'resultado',)
        }),
        ('Dados de Preenchimento', {
            'fields': ('dados_preenchimento',),
            'classes': ('collapse',)
        }),
        ('Laudo Gerado', {
            'fields': ('laudo_texto',),
            'description': 'Texto completo do laudo gerado'
        }),
        ('Arquivos', {
            'fields': ('pdf_arquivo',),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('gerado_por', 'gerado_em')
        }),
    )
    
    actions = ['exportar_pdf', 'marcar_como_finalizado']
    
    def exportar_pdf(self, request, queryset):
        """Exporta laudos selecionados para PDF"""
        count = 0
        for laudo in queryset:
            if not laudo.pdf_arquivo:
                # TODO: Implementar geração de PDF
                self.message_user(request, f'⚠️ Geração de PDF ainda não implementada para "{laudo}"', level='WARNING')
            else:
                count += 1
        
        if count > 0:
            self.message_user(request, f'✅ {count} laudo(s) já possuem PDF!')
    
    exportar_pdf.short_description = '📄 Exportar para PDF'
    
    def marcar_como_finalizado(self, request, queryset):
        """Marca laudos como finalizados"""
        updated = queryset.update(status='finalizado')
        self.message_user(request, f'✅ {updated} laudo(s) marcado(s) como finalizado!')
    
    marcar_como_finalizado.short_description = '✓ Marcar como finalizado'