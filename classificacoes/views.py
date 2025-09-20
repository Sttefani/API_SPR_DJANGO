# classificacoes/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ClassificacaoOcorrencia
from .serializers import ClassificacaoOcorrenciaSerializer, ClassificacaoOcorrenciaLixeiraSerializer
from .permissions import ClassificacaoPermission

class ClassificacaoOcorrenciaViewSet(viewsets.ModelViewSet):
    queryset = ClassificacaoOcorrencia.all_objects.select_related('parent').all()
    permission_classes = [ClassificacaoPermission]
    filterset_fields = ['codigo', 'nome', 'parent'] # Filtro por código, nome e ID do pai

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return ClassificacaoOcorrenciaLixeiraSerializer
        return ClassificacaoOcorrenciaSerializer

    def list(self, request, *args, **kwargs):
        queryset = ClassificacaoOcorrencia.objects.select_related('parent').all()
        queryset = self.filter_queryset(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # ... (copie os métodos perform_create, perform_update, destroy, lixeira, restaurar das outras views, como a de Cidades)
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
        lixeira_qs = ClassificacaoOcorrencia.all_objects.filter(deleted_at__isnull=False)
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)