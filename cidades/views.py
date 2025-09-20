# cidades/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Cidade
from .serializers import CidadeSerializer, CidadeLixeiraSerializer
from .permissions import CidadePermission # Importando nossa nova permissão

class CidadeViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para gerenciar Cidades.
    - Todos os usuários autenticados podem criar, listar e editar.
    - Apenas Super Admin pode deletar (soft delete).
    """
    queryset = Cidade.all_objects.all() # O queryset base vê todos os objetos
    permission_classes = [CidadePermission] # Aplicando nossa regra de permissão customizada
    filterset_fields = ['nome']

    def get_serializer_class(self):
        # Usa o serializer correto dependendo da ação (lixeira ou normal)
        if self.action == 'lixeira':
            return CidadeLixeiraSerializer
        return CidadeSerializer

    def list(self, request, *args, **kwargs):
        # A lista principal mostra apenas as cidades não deletadas
        queryset = Cidade.objects.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        # CORREÇÃO AQUI
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        # E CORREÇÃO AQUI
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        lixeira_qs = Cidade.all_objects.filter(deleted_at__isnull=False).order_by('-deleted_at')
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'detail': 'Esta cidade não está deletada.'}, status=status.HTTP_400_BAD_REQUEST)
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)