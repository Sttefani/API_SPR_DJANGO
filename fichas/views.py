# fichas/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from .permissions import FichaPermission
from .models import (
    FichaLocalCrime, Vitima, Vestigio,
    FichaAcidenteTransito, Veiculo,
    FichaConstatacaoSubstancia, ItemSubstancia, Lacre,
    FichaDocumentoscopia, ItemDocumentoscopia,
    FichaMaterialDiverso, ItemMaterial
)
from .serializers import (
    FichaLocalCrimeSerializer, VitimaSerializer, VestigioSerializer,
    FichaAcidenteTransitoSerializer, VeiculoSerializer,
    FichaConstatacaoSubstanciaSerializer, ItemSubstanciaSerializer, LacreSerializer,
    FichaDocumentoscopiaSerializer, ItemDocumentoscopiaSerializer,
    FichaMaterialDiversoSerializer, ItemMaterialSerializer
)
from .filters import FichaLocalCrimeFilter


class BaseFichaCRUDViewSet(viewsets.ModelViewSet):
    permission_classes = [FichaPermission]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request, *args, **kwargs):
        # get_queryset() já filtra pelo pai, então aqui só pegamos os deletados
        queryset = self.get_queryset().model.all_objects.filter(
            deleted_at__isnull=False, **self.kwargs
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, *args, **kwargs):
        instance = self.get_queryset().model.all_objects.get(pk=kwargs.get('pk'))
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# =============================================================================
# VIEWSETS PARA AS FICHAS PRINCIPAIS (NÍVEL 2 - ANINHADAS EM OCORRÊNCIAS)
# =============================================================================
class FichaLocalCrimeViewSet(BaseFichaCRUDViewSet):
    queryset = FichaLocalCrime.all_objects.all()
    serializer_class = FichaLocalCrimeSerializer
    filterset_class = FichaLocalCrimeFilter
    
    def get_queryset(self):
        return self.queryset.filter(ocorrencia_id=self.kwargs['ocorrencia_pk'])

    def perform_create(self, serializer):
        serializer.save(ocorrencia_id=self.kwargs['ocorrencia_pk'], created_by=self.request.user)

class FichaAcidenteTransitoViewSet(BaseFichaCRUDViewSet):
    queryset = FichaAcidenteTransito.all_objects.all()
    serializer_class = FichaAcidenteTransitoSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ocorrencia_id=self.kwargs['ocorrencia_pk'])

    def perform_create(self, serializer):
        serializer.save(ocorrencia_id=self.kwargs['ocorrencia_pk'], created_by=self.request.user)

class FichaConstatacaoSubstanciaViewSet(BaseFichaCRUDViewSet):
    queryset = FichaConstatacaoSubstancia.all_objects.all()
    serializer_class = FichaConstatacaoSubstanciaSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ocorrencia_id=self.kwargs['ocorrencia_pk'])

    def perform_create(self, serializer):
        serializer.save(ocorrencia_id=self.kwargs['ocorrencia_pk'], created_by=self.request.user)

class FichaDocumentoscopiaViewSet(BaseFichaCRUDViewSet):
    queryset = FichaDocumentoscopia.all_objects.all()
    serializer_class = FichaDocumentoscopiaSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ocorrencia_id=self.kwargs['ocorrencia_pk'])

    def perform_create(self, serializer):
        serializer.save(ocorrencia_id=self.kwargs['ocorrencia_pk'], created_by=self.request.user)
        
class FichaMaterialDiversoViewSet(BaseFichaCRUDViewSet):
    queryset = FichaMaterialDiverso.all_objects.all()
    serializer_class = FichaMaterialDiversoSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ocorrencia_id=self.kwargs['ocorrencia_pk'])

    def perform_create(self, serializer):
        serializer.save(ocorrencia_id=self.kwargs['ocorrencia_pk'], created_by=self.request.user)


# =============================================================================
# VIEWSETS PARA OS SUB-ITENS (NÍVEL 3 - ANINHADAS NAS FICHAS)
# =============================================================================
class VitimaViewSet(BaseFichaCRUDViewSet):
    queryset = Vitima.all_objects.all()
    serializer_class = VitimaSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ficha_id=self.kwargs['fichalocalcrime_pk'])

    def perform_create(self, serializer):
        serializer.save(ficha_id=self.kwargs['fichalocalcrime_pk'], created_by=self.request.user)

class VestigioViewSet(BaseFichaCRUDViewSet):
    queryset = Vestigio.all_objects.all()
    serializer_class = VestigioSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ficha_id=self.kwargs['fichalocalcrime_pk'])

    def perform_create(self, serializer):
        serializer.save(ficha_id=self.kwargs['fichalocalcrime_pk'], created_by=self.request.user)

class VeiculoViewSet(BaseFichaCRUDViewSet):
    queryset = Veiculo.all_objects.all()
    serializer_class = VeiculoSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ficha_acidente_id=self.kwargs['fichaacidentetransito_pk'])

    def perform_create(self, serializer):
        serializer.save(ficha_acidente_id=self.kwargs['fichaacidentetransito_pk'], created_by=self.request.user)

class ItemSubstanciaViewSet(BaseFichaCRUDViewSet):
    queryset = ItemSubstancia.all_objects.all()
    serializer_class = ItemSubstanciaSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ficha_id=self.kwargs['fichaconstatacaosubstancia_pk'])

    def perform_create(self, serializer):
        serializer.save(ficha_id=self.kwargs['fichaconstatacaosubstancia_pk'], created_by=self.request.user)

class LacreViewSet(BaseFichaCRUDViewSet):
    queryset = Lacre.all_objects.all()
    serializer_class = LacreSerializer
    
    def get_queryset(self):
        if 'fichaconstatacaosubstancia_pk' in self.kwargs:
            return self.queryset.filter(ficha_substancia_id=self.kwargs['fichaconstatacaosubstancia_pk'])
        if 'vestigio_pk' in self.kwargs: # Corrigido para 'vestigio_pk'
            return self.queryset.filter(vestigio_id=self.kwargs['vestigio_pk'])
        return self.queryset.none()

    def perform_create(self, serializer):
        if 'fichaconstatacaosubstancia_pk' in self.kwargs:
            serializer.save(ficha_substancia_id=self.kwargs['fichaconstatacaosubstancia_pk'], created_by=self.request.user)
        elif 'vestigio_pk' in self.kwargs: # Corrigido para 'vestigio_pk'
            serializer.save(vestigio_id=self.kwargs['vestigio_pk'], created_by=self.request.user)

class ItemDocumentoscopiaViewSet(BaseFichaCRUDViewSet):
    queryset = ItemDocumentoscopia.all_objects.all()
    serializer_class = ItemDocumentoscopiaSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ficha_id=self.kwargs['fichadocumentoscopia_pk'])

    def perform_create(self, serializer):
        serializer.save(ficha_id=self.kwargs['fichadocumentoscopia_pk'], created_by=self.request.user)

class ItemMaterialViewSet(BaseFichaCRUDViewSet):
    queryset = ItemMaterial.all_objects.all()
    serializer_class = ItemMaterialSerializer
    
    def get_queryset(self):
        return self.queryset.filter(ficha_id=self.kwargs['fichamaterialdiverso_pk'])

    def perform_create(self, serializer):
        serializer.save(ficha_id=self.kwargs['fichamaterialdiverso_pk'], created_by=self.request.user)
        
# fichas/views.py

# ... (imports)

# =============================================================================
# VIEWSET BASE (COM LIXEIRA E RESTAURAÇÃO CORRIGIDAS)
# =============================================================================
class BaseFichaCRUDViewSet(viewsets.ModelViewSet):
    """
    ViewSet base que inclui a lógica completa de CRUD, Soft Delete,
    Lixeira e Restauração para ser herdada por todas as outras.
    """
    permission_classes = [FichaPermission]

    def get_queryset(self):
        """
        Sobrescreve o queryset base para usar all_objects, permitindo que
        actions como 'retrieve' e 'restaurar' encontrem itens deletados.
        A filtragem de itens ativos para a lista principal será feita no método 'list'.
        """
        return self.queryset.model.all_objects.all()

    def list(self, request, *args, **kwargs):
        """
        Sobrescreve a ação 'list' para mostrar apenas os itens ATIVOS.
        """
        # Pega o queryset filtrado pelos pais (se for uma view aninhada)
        parent_filtered_queryset = self.filter_queryset(self.get_queryset())
        # Aplica o filtro final para pegar apenas os não-deletados
        active_queryset = parent_filtered_queryset.filter(deleted_at__isnull=True)
        
        serializer = self.get_serializer(active_queryset, many=True)
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
    def lixeira(self, request, *args, **kwargs):
        """
        Mostra os itens na lixeira, respeitando os filtros de aninhamento.
        """
        parent_filtered_queryset = self.filter_queryset(self.get_queryset())
        deleted_queryset = parent_filtered_queryset.filter(deleted_at__isnull=False)
        
        serializer = self.get_serializer(deleted_queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, *args, **kwargs):
        """
        Restaura um item da lixeira. get_object() já funciona
        porque o get_queryset() agora vê todos os objetos.
        """
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'error': 'Este item não está na lixeira.'}, status=status.HTTP_400_BAD_REQUEST)
            
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)