from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ProcedimentoCadastrado
from .serializers import ProcedimentoCadastradoSerializer, ProcedimentoCadastradoLixeiraSerializer
from .permissions import ProcedimentoCadastradoPermission

class ProcedimentoCadastradoViewSet(viewsets.ModelViewSet):
    queryset = ProcedimentoCadastrado.objects.select_related('tipo_procedimento').all().order_by('-ano', '-numero')
    permission_classes = [ProcedimentoCadastradoPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['numero', 'ano', 'tipo_procedimento__sigla', 'tipo_procedimento__nome']
    
    def get_queryset(self):
        """Sobrescreve queryset para actions específicas"""
        if self.action in ['restaurar', 'lixeira']:
            return ProcedimentoCadastrado.all_objects.select_related('tipo_procedimento').all()
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return ProcedimentoCadastradoLixeiraSerializer
        return ProcedimentoCadastradoSerializer

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
        lixeira_qs = ProcedimentoCadastrado.all_objects.select_related('tipo_procedimento').filter(deleted_at__isnull=False).order_by('-deleted_at')
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'detail': 'Este procedimento não está deletado.'}, status=status.HTTP_400_BAD_REQUEST)
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)