from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ClassificacaoOcorrencia
from .serializers import ClassificacaoOcorrenciaSerializer, ClassificacaoOcorrenciaLixeiraSerializer
from .permissions import ClassificacaoPermission

class ClassificacaoOcorrenciaViewSet(viewsets.ModelViewSet):
    queryset = ClassificacaoOcorrencia.objects.select_related('parent').all()
    serializer_class = ClassificacaoOcorrenciaSerializer
    permission_classes = [ClassificacaoPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['codigo', 'nome']
    pagination_class = None  # ← DESABILITA PAGINAÇÃO
    
    def get_queryset(self):
        if self.action in ['restaurar', 'lixeira']:
            return ClassificacaoOcorrencia.all_objects.select_related('parent').all()
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return ClassificacaoOcorrenciaLixeiraSerializer
        return ClassificacaoOcorrenciaSerializer

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
        lixeira_qs = ClassificacaoOcorrencia.all_objects.select_related('parent').filter(deleted_at__isnull=False).order_by('-deleted_at')
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'detail': 'Esta classificação não está deletada.'}, status=status.HTTP_400_BAD_REQUEST)
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)