# exames/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Exame
from .serializers import ExameSerializer, ExameLixeiraSerializer
from .permissions import ExamePermission

class ExameViewSet(viewsets.ModelViewSet):
    queryset = Exame.all_objects.select_related('parent', 'servico_pericial').all()
    permission_classes = [ExamePermission]
    # Filtros para o frontend poder buscar exames por serviço, por pai, etc.
    filterset_fields = ['codigo', 'nome', 'servico_pericial', 'parent']

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return ExameLixeiraSerializer
        return ExameSerializer

    def list(self, request, *args, **kwargs):
        queryset = Exame.objects.select_related('parent', 'servico_pericial').all()
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
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        lixeira_qs = Exame.all_objects.filter(deleted_at__isnull=False)
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)