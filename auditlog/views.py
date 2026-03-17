"""
# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025
"""

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from .models import AuditLog
from .serializers import AuditLogSerializer

PERFIS_PERMITIDOS = {'SUPER_ADMIN', 'ADMINISTRATIVO'}


class AuditLogViewSet(ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)

        if not (user.is_superuser or perfil in PERFIS_PERMITIDOS):
            return AuditLog.objects.none()

        qs = AuditLog.objects.select_related('usuario').all()

        usuario_id = self.request.query_params.get('usuario_id')
        acao = self.request.query_params.get('acao')
        modulo = self.request.query_params.get('modulo')
        data_inicio = self.request.query_params.get('data_inicio')
        data_fim = self.request.query_params.get('data_fim')
        busca = self.request.query_params.get('busca')

        if usuario_id:
            qs = qs.filter(usuario_id=usuario_id)
        if acao:
            qs = qs.filter(acao=acao)
        if modulo:
            qs = qs.filter(app_label=modulo)
        if data_inicio:
            qs = qs.filter(timestamp__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(timestamp__date__lte=data_fim)
        if busca:
            from django.db.models import Q
            qs = qs.filter(
                Q(objeto_repr__icontains=busca) |
                Q(modelo__icontains=busca)
            )

        return qs
