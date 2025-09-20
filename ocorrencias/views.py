# ocorrencias/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, permission_classes
import datetime
from django.utils import timezone  # Importe o timezone do Django
from .models import Ocorrencia
from .serializers import OcorrenciaListSerializer, OcorrenciaDetailSerializer, OcorrenciaUpdateSerializer
from .permissions import OcorrenciaPermission, PodeFinalizarOcorrencia


class OcorrenciaViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para gerenciar Ocorrências.
    """
    queryset = Ocorrencia.all_objects.select_related(
        'servico_pericial', 'unidade_demandante', 'autoridade', 'cidade', 'classificacao', 'created_by'
    ).prefetch_related('exames_solicitados').all()

    permission_classes = [OcorrenciaPermission]
    filterset_fields = [
        'numero_ocorrencia', 'status', 'servico_pericial', 'unidade_demandante',
        'autoridade', 'cidade', 'perito_atribuido'
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return OcorrenciaListSerializer
        if self.action in ['update', 'partial_update']:
            return OcorrenciaUpdateSerializer
        return OcorrenciaDetailSerializer

    def get_queryset(self):
        user = self.request.user
        # O queryset base já é definido na classe, aqui apenas aplicamos o filtro de permissão
        if user.is_superuser or user.perfil == 'ADMINISTRATIVO':
            return self.queryset

        # Outros perfis veem apenas ocorrências dos seus serviços periciais
        return self.queryset.filter(servico_pericial__in=user.servicos_periciais.all())

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
        queryset = self.get_queryset().filter(deleted_at__isnull=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    @permission_classes([PodeFinalizarOcorrencia])
    def finalizar(self, request, pk=None):
        ocorrencia = self.get_object()
        if ocorrencia.status == 'FINALIZADA':
            return Response({'detail': 'Esta ocorrência já está finalizada.'}, status=status.HTTP_400_BAD_REQUEST)

        ocorrencia.status = Ocorrencia.Status.FINALIZADA
        ocorrencia.data_finalizacao = timezone.now()
        ocorrencia.save()

        serializer = self.get_serializer(ocorrencia)
        return Response(serializer.data)