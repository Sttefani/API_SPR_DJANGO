# ordens_servico/views.py

from rest_framework import viewsets, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from .models import OrdemServico
from .serializers import (
    OrdemServicoSerializer, 
    CriarOrdemServicoSerializer, 
    TomarCienciaSerializer
)
from .permissions import OrdemServicoPermission
from .filters import OrdemServicoFilter
from ocorrencias.models import Ocorrencia

class OrdemServicoViewSet(viewsets.ModelViewSet):
    """
    Endpoint para gerenciar Ordens de Serviço aninhadas em Ocorrências.
    """
    queryset = OrdemServico.all_objects.select_related(
        'ocorrencia', 'created_by', 'ciente_por'
    ).all()
    
    permission_classes = [OrdemServicoPermission]
    filterset_class = OrdemServicoFilter

    def get_queryset(self):
        """
        Filtra o queryset com base no usuário e no aninhamento da URL.
        """
        user = self.request.user
        
        # Filtra pela ocorrência pai da URL
        queryset = self.queryset.filter(ocorrencia_id=self.kwargs.get('ocorrencia_pk'))

        # Super Admin e Admin veem todas as OS daquela ocorrência
        if user.is_superuser or user.perfil == 'ADMINISTRATIVO':
            return queryset
        
        # Perito vê apenas as OS de ocorrências que lhe foram atribuídas
        return queryset.filter(ocorrencia__perito_atribuido=user)

    def get_serializer_class(self):
        """
        Retorna o serializer correto para cada ação.
        """
        if self.action == 'create':
            return CriarOrdemServicoSerializer
        if self.action == 'tomar_ciencia':
            return TomarCienciaSerializer
        # Para list, retrieve, update, etc.
        return OrdemServicoSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Cria uma nova Ordem de Serviço, passando o contexto correto para o serializer.
        """
        ocorrencia_id = self.kwargs.get('ocorrencia_pk')
        try:
            ocorrencia = Ocorrencia.objects.get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            return Response({"error": "Ocorrência não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if ocorrencia.status == Ocorrencia.Status.FINALIZADA:
            return Response(
                {"error": "Não é possível emitir Ordem de Serviço para uma ocorrência que já foi finalizada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Instancia o serializer, passando a request e a ocorrência no CONTEXTO
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'ocorrencia': ocorrencia}
        )
        serializer.is_valid(raise_exception=True)
        
        # O método .create() do serializer agora terá acesso ao contexto
        serializer.save()
        
        # Retorna a OS recém-criada usando o serializer de visualização
        response_serializer = OrdemServicoSerializer(serializer.instance)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        
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
        instance = self.get_queryset().model.all_objects.get(pk=kwargs.get('pk'))
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'])
    def tomar_ciencia(self, request, ocorrencia_pk=None, pk=None):
        """
        Permite que o perito destinatário tome ciência da Ordem de Serviço.
        """
        ordem_servico = self.get_object()
        
        if request.user != ordem_servico.ocorrencia.perito_atribuido:
            return Response(
                {"error": "Apenas o perito atribuído à ocorrência pode tomar ciência desta OS."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if ordem_servico.ciente_por:
            return Response(
                {"message": "Ciência já registrada para esta Ordem de Serviço."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if request.method == 'POST':
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
            ordem_servico.tomar_ciencia(user=request.user, ip_address=ip_address)
            
            response_serializer = OrdemServicoSerializer(ordem_servico)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        return Response()

    @action(detail=True, methods=['post'])
    def concluir(self, request, ocorrencia_pk=None, pk=None):
        """
        Permite que um Admin/Super Admin marque uma OS como concluída.
        """
        ordem_servico = self.get_object()
        
        ordem_servico.status = OrdemServico.Status.CONCLUIDA
        ordem_servico.data_conclusao = timezone.now()
        ordem_servico.save()
        
        serializer = self.get_serializer(ordem_servico)
        return Response(serializer.data, status=status.HTTP_200_OK)