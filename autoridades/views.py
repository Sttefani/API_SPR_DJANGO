# autoridades/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Autoridade
from .serializers import AutoridadeSerializer, AutoridadeLixeiraSerializer
from .permissions import AutoridadePermission

class AutoridadeViewSet(viewsets.ModelViewSet):
    queryset = Autoridade.all_objects.select_related('cargo').all()
    permission_classes = [AutoridadePermission]
    filterset_fields = ['nome', 'cargo__nome'] # Filtros por nome da autoridade e nome do cargo

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return AutoridadeLixeiraSerializer
        return AutoridadeSerializer

    def list(self, request, *args, **kwargs):
        queryset = Autoridade.objects.select_related('cargo').all()
        # Aplicando o filtro manualmente para a lista
        queryset = self.filter_queryset(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=self.request.user)
        return Response(status=status.HTTP_24_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        lixeira_qs = Autoridade.all_objects.filter(deleted_at__isnull=False)
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)