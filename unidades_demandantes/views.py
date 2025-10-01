from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import UnidadeDemandante
from .serializers import UnidadeDemandanteSerializer, UnidadeDemandanteLixeiraSerializer
from .permissions import UnidadeDemandantePermission

class UnidadeDemandanteViewSet(viewsets.ModelViewSet):
    queryset = UnidadeDemandante.objects.all().order_by('sigla')
    permission_classes = [UnidadeDemandantePermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['sigla', 'nome']
    
    def get_queryset(self):
        """Sobrescreve queryset para actions específicas"""
        if self.action in ['restaurar', 'lixeira']:
            return UnidadeDemandante.all_objects.all()
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return UnidadeDemandanteLixeiraSerializer
        return UnidadeDemandanteSerializer

    @action(detail=False, methods=['get'])
    def dropdown(self, request):
        """Retorna TODAS as unidades para uso em dropdowns (sem paginação)"""
        queryset = UnidadeDemandante.objects.all().order_by('sigla')
        serializer = UnidadeDemandanteSerializer(queryset, many=True)
        return Response(serializer.data)

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
        lixeira_qs = UnidadeDemandante.all_objects.filter(deleted_at__isnull=False).order_by('-deleted_at')
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'detail': 'Esta unidade não está deletada.'}, status=status.HTTP_400_BAD_REQUEST)
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)