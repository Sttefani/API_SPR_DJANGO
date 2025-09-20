# servicos_periciais/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ServicoPericial
from .serializers import ServicoPericialSerializer, ServicoPericialLixeiraSerializer
from usuarios.permissions import IsSuperAdminUser


class ServicoPericialViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para o Super Admin gerenciar os Serviços Periciais.
    """
    # 1. A MUDANÇA PRINCIPAL: O queryset agora vê TODOS os objetos, incluindo os deletados.
    queryset = ServicoPericial.all_objects.all().order_by('sigla')
    serializer_class = ServicoPericialSerializer
    permission_classes = [IsSuperAdminUser]
    filterset_fields = ['sigla', 'nome'] # <-- Adicione esta linha


    # 2. MÉTODO NOVO: Este método filtra a lista principal para mostrar apenas os ativos.
    def list(self, request, *args, **kwargs):
        # Usamos .objects aqui para pegar apenas os não deletados para a lista.
        queryset = ServicoPericial.objects.all().order_by('sigla')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        """
        Endpoint para listar todos os serviços que foram 'soft deleted'.
        """
        lixeira_qs = ServicoPericial.all_objects.filter(deleted_at__isnull=False).order_by('-deleted_at')

        # USE O NOVO SERIALIZER AQUI
        serializer = ServicoPericialLixeiraSerializer(lixeira_qs, many=True, context={'request': request})

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        """
        Endpoint para listar todos os serviços que foram 'soft deleted'.
        """
        lixeira_qs = ServicoPericial.all_objects.filter(deleted_at__isnull=False).order_by('-deleted_at')
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        """
        Endpoint para restaurar um serviço que foi 'soft deleted'.
        """
        instance = self.get_object()  # Agora get_object() funciona, pois o queryset principal vê tudo.

        if instance.deleted_at is None:
            return Response({'detail': 'Este serviço não está deletado.'}, status=status.HTTP_400_BAD_REQUEST)

        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)