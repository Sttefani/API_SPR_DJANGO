# movimentacoes/views.py

from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Movimentacao
from .serializers import MovimentacaoSerializer, CriarMovimentacaoSerializer
from .permissions import MovimentacaoPermission
from .filters import MovimentacaoFilter
from ocorrencias.models import Ocorrencia

class MovimentacaoViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    """
    Endpoint para gerenciar o histórico de movimentações de uma ocorrência.
    """
    queryset = Movimentacao.all_objects.all()
    permission_classes = [MovimentacaoPermission]
    filterset_class = MovimentacaoFilter

    def get_serializer_class(self):
        if self.action == 'create':
            return CriarMovimentacaoSerializer
        return MovimentacaoSerializer
    
    def get_queryset(self):
        # Filtra as movimentações para pertencerem apenas à ocorrência da URL
        return self.queryset.filter(ocorrencia_id=self.kwargs.get('ocorrencia_pk'))
    
    def create(self, request, *args, **kwargs):
        """
        Cria uma nova movimentação com assinatura.
        """
        ocorrencia_id = self.kwargs.get('ocorrencia_pk')
        try:
            ocorrencia = Ocorrencia.objects.get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            return Response({"error": "Ocorrência não encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'ocorrencia': ocorrencia}
        )
        
        serializer.is_valid(raise_exception=True)
        movimentacao = serializer.save() # O método create do serializer já salva tudo
        
        # Retorna os dados usando o serializer de visualização
        response_serializer = MovimentacaoSerializer(movimentacao, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    # --- LÓGICA DE DELEÇÃO E LIXEIRA ADICIONADA ---
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request, *args, **kwargs):
        queryset = self.get_queryset().filter(deleted_at__isnull=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)