"""
# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025
"""

from rest_framework.routers import DefaultRouter
from .views import AuditLogViewSet

router = DefaultRouter()
router.register(r'', AuditLogViewSet, basename='auditlog')

urlpatterns = router.urls
