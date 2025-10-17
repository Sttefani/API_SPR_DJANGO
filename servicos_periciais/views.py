from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from servicos_periciais.permissions import ServicoPericialPermission
from .models import ServicoPericial
from .serializers import ServicoPericialSerializer, ServicoPericialLixeiraSerializer
from rest_framework.permissions import SAFE_METHODS
from usuarios.permissions import IsSuperAdminUser
from rest_framework import viewsets, filters  # ← Certifique-se que filters está aqui


class ServicoPericialViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para o Super Admin gerenciar os Serviços Periciais.
    """
    queryset = ServicoPericial.objects.all().order_by('sigla')
    serializer_class = ServicoPericialSerializer
    permission_classes = [ServicoPericialPermission]  # ← MUDE AQUI
    filter_backends = [filters.SearchFilter]  # ← ADICIONE
    filterset_fields = ['sigla', 'nome']
    search_fields = ['sigla', 'nome']  # ← ADICIONE
    pagination_class = None  # ← ADICIONE (esta é a linha crítica)
    
    # ← ADICIONE ESTE MÉTODO
    def get_queryset(self):
        """
        Retorna queryset apropriado:
        - Para lixeira e restaurar: inclui objetos deletados
        - Para outras actions: apenas objetos ativos
        """
        if self.action in ['lixeira', 'restaurar']:
            return ServicoPericial.all_objects.all().order_by('sigla')
        return ServicoPericial.objects.all().order_by('sigla')
    
    
    # ← REMOVI o método list() customizado para usar paginação padrão
    def has_permission(self, request, view):
        # Se o método for de leitura (GET, HEAD, OPTIONS), permite o acesso.
        if request.method in SAFE_METHODS:
            return True

        # Para todos os outros métodos (escrita), verifica se o utilizador é super admin.
        return IsSuperAdminUser().has_permission(request, view)

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
        serializer = ServicoPericialLixeiraSerializer(lixeira_qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        """
        Endpoint para restaurar um serviço que foi 'soft deleted'.
        """
        instance = self.get_object()

        if instance.deleted_at is None:
            return Response({'detail': 'Este serviço não está deletado.'}, status=status.HTTP_400_BAD_REQUEST)

        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], pagination_class=None)
    def dropdown(self, request):
        queryset = self.get_queryset().order_by('nome')  # ou outro campo apropriado
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)