from rest_framework import viewsets, mixins, status  # ← ESTA LINHA
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import Movimentacao
from .serializers import MovimentacaoSerializer, CriarMovimentacaoSerializer
from .permissions import MovimentacaoPermission
from .filters import MovimentacaoFilter
from ocorrencias.models import Ocorrencia
from .pdf_generator import gerar_pdf_movimentacao, gerar_pdf_historico_movimentacoes



class MovimentacaoViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    queryset = Movimentacao.all_objects.all()
    permission_classes = [MovimentacaoPermission]
    filterset_class = MovimentacaoFilter

    def get_serializer_class(self):
        if self.action == 'create':
            return CriarMovimentacaoSerializer
        return MovimentacaoSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ocorrencia_id=self.kwargs.get('ocorrencia_pk'))
    
    def create(self, request, *args, **kwargs):
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
        movimentacao = serializer.save()
        
        response_serializer = MovimentacaoSerializer(movimentacao, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """
        Atualiza uma movimentação existente (requer assinatura)
        """
        instance = self.get_object()
        
        # Usa o serializer de criação que tem validação de assinatura
        serializer = CriarMovimentacaoSerializer(
            data=request.data,
            context={
                'request': request, 
                'ocorrencia': instance.ocorrencia,
                'movimentacao': instance  # ← PASSA PARA VALIDAÇÃO
            }
        )
        
        serializer.is_valid(raise_exception=True)
        
        # Atualiza os campos
        instance.assunto = serializer.validated_data.get('assunto', instance.assunto)
        instance.descricao = serializer.validated_data.get('descricao', instance.descricao)
        instance.updated_by = request.user
        instance.save()
        
        # Retorna usando o serializer de visualização
        response_serializer = MovimentacaoSerializer(instance, context={'request': request})
        return Response(response_serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """
        PATCH também usa o mesmo fluxo de validação
        """
        return self.update(request, *args, **kwargs)

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
        
    @action(detail=True, methods=['get'], url_path='pdf')
    def gerar_pdf(self, request, *args, **kwargs):
        movimentacao = self.get_object()
        return gerar_pdf_movimentacao(movimentacao, request)
    
    @action(detail=False, methods=['get'], url_path='historico-pdf')
    def gerar_historico_pdf(self, request, *args, **kwargs):
        ocorrencia_id = self.kwargs.get('ocorrencia_pk')
        try:
            ocorrencia = Ocorrencia.objects.get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            return Response({"error": "Ocorrência não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        
        return gerar_pdf_historico_movimentacoes(ocorrencia, request)