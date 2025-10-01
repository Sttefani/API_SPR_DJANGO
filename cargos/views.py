# cargos/views.py

from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Cargo
from .serializers import CargoSerializer, CargoLixeiraSerializer
from .permissions import CargoPermission

class CargoViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para gerenciar Cargos.
    - Todos os usuários autenticados podem criar, listar e editar.
    - Apenas Super Admin pode deletar (soft delete).
    """
    queryset = Cargo.objects.all().order_by('nome')
    permission_classes = [CargoPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nome']

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return CargoLixeiraSerializer
        return CargoSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        lixeira_qs = Cargo.all_objects.filter(deleted_at__isnull=False).order_by('-deleted_at')
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'detail': 'Este cargo não está deletado.'}, status=status.HTTP_400_BAD_REQUEST)
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)