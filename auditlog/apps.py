"""
# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025
"""

from django.apps import AppConfig


class AuditlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditlog'
    verbose_name = 'Auditoria'

    def ready(self):
        from django.db.models.signals import post_save, post_delete
        from django.apps import apps
        from .signals import handle_save, handle_delete, AUDITED_APPS

        for app_config in apps.get_app_configs():
            if app_config.name in AUDITED_APPS:
                for model in app_config.get_models():
                    post_save.connect(handle_save, sender=model, weak=False)
                    post_delete.connect(handle_delete, sender=model, weak=False)
