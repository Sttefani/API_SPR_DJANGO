# custodia/views.py

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Vestigio, VestigioMovimentacao, DNA
from .serializers import (
    VestigioListSerializer,
    VestigioDetailSerializer,
    VestigioCreateSerializer,
    FinalizarVestigioSerializer,
    VestigioMovimentacaoListSerializer,
    VestigioMovimentacaoCreateSerializer,
    DNAListSerializer,
    DNADetailSerializer,
    DNACreateSerializer,
)
from .permissions import PodeCustodiar, PodeVerCustodia
from .pdf_generator import gerar_ficha_vestigio, gerar_ficha_dna
from .filters import VestigioFilter, DNAFilter
from usuarios.models import User


def _is_externo(user):
    return user.perfil == User.Perfil.EXTERNO


# ---------------------------------------------------------------------------
# Vestígio
# ---------------------------------------------------------------------------

class VestigioViewSet(viewsets.ModelViewSet):
    permission_classes = [PodeVerCustodia]
    filterset_class = VestigioFilter

    def get_queryset(self):
        qs = Vestigio.objects.select_related(
            'unidade_demandante',
            'servico_pericial',
            'autoridade__cargo',
            'user_destino',
            'created_by',
            'updated_by',
        ).prefetch_related('procedimentos')

        # Regra EXTERNO: vê apenas vestígios da sua unidade_demandante
        user = self.request.user
        if _is_externo(user) and user.unidade_demandante:
            qs = qs.filter(unidade_demandante=user.unidade_demandante)

        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return VestigioListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return VestigioCreateSerializer
        return VestigioDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                            'finalizar', 'reabrir'):
            return [PodeCustodiar()]
        return [PodeVerCustodia()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    @action(detail=True, methods=['post'], url_path='finalizar')
    def finalizar(self, request, pk=None):
        vestigio = self.get_object()
        serializer = FinalizarVestigioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vestigio.status = Vestigio.Status.FINALIZADO
        vestigio.saiu_da_custodia = serializer.validated_data['saiu_da_custodia']
        if serializer.validated_data.get('descricao'):
            vestigio.descricao = serializer.validated_data['descricao']
        vestigio.updated_by = request.user
        vestigio.save()

        return Response(VestigioDetailSerializer(vestigio).data)

    @action(detail=True, methods=['post'], url_path='reabrir')
    def reabrir(self, request, pk=None):
        vestigio = self.get_object()
        vestigio.status = Vestigio.Status.ANDAMENTO
        vestigio.saiu_da_custodia = False
        vestigio.updated_by = request.user
        vestigio.save()
        return Response(VestigioDetailSerializer(vestigio).data)

    @action(detail=True, methods=['get'], url_path='movimentacoes')
    def movimentacoes(self, request, pk=None):
        vestigio = self.get_object()
        movs = VestigioMovimentacao.objects.filter(
            vestigio=vestigio
        ).select_related(
            'unidade_demandante', 'servico_pericial',
            'autoridade', 'user_destino', 'created_by',
        ).order_by('-created_at')
        serializer = VestigioMovimentacaoListSerializer(movs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='dnas')
    def dnas(self, request, pk=None):
        vestigio = self.get_object()
        dnas = DNA.objects.filter(vestigio=vestigio).select_related(
            'perito', 'created_by'
        ).order_by('-created_at')
        serializer = DNAListSerializer(dnas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='ficha-pdf')
    def ficha_pdf(self, request, pk=None):
        """Gera a Ficha de Acompanhamento do Vestígio em PDF com QR code."""
        vestigio = self.get_object()
        return gerar_ficha_vestigio(vestigio, request)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'inicial': qs.filter(status=Vestigio.Status.INICIAL).count(),
            'andamento': qs.filter(status=Vestigio.Status.ANDAMENTO).count(),
            'finalizado': qs.filter(status=Vestigio.Status.FINALIZADO).count(),
            'biologicos': qs.filter(biologico=True).count(),
        })


# ---------------------------------------------------------------------------
# Movimentação de Vestígio
# ---------------------------------------------------------------------------

class VestigioMovimentacaoViewSet(viewsets.ModelViewSet):
    permission_classes = [PodeVerCustodia]

    def get_queryset(self):
        return VestigioMovimentacao.objects.select_related(
            'vestigio', 'unidade_demandante', 'servico_pericial',
            'autoridade', 'user_destino', 'created_by',
        ).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return VestigioMovimentacaoCreateSerializer
        return VestigioMovimentacaoListSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [PodeCustodiar()]
        return [PodeVerCustodia()]

    def perform_create(self, serializer):
        movimentacao = serializer.save(created_by=self.request.user)
        vestigio = movimentacao.vestigio
        if vestigio.status == Vestigio.Status.INICIAL:
            vestigio.status = Vestigio.Status.ANDAMENTO
            vestigio.updated_by = self.request.user
            vestigio.save()

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    @action(detail=True, methods=['post'], url_path='aceitar')
    def aceitar(self, request, pk=None):
        movimentacao = self.get_object()
        if movimentacao.aceito:
            return Response(
                {'detail': 'Movimentação já foi aceita.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        movimentacao.aceito = True
        movimentacao.data_hora_aceito = timezone.now()
        movimentacao.save()
        return Response(VestigioMovimentacaoListSerializer(movimentacao).data)


# ---------------------------------------------------------------------------
# DNA
# ---------------------------------------------------------------------------

class DNAViewSet(viewsets.ModelViewSet):
    """
    Regras de negócio (espelhadas do SPR-Custódia Java):
    - EXTERNO: pode criar (situacao forçado p/ NAO_APENADO, flag externo=True),
               NÃO pode editar nem deletar registros existentes,
               vê apenas DNAs vinculados aos vestígios da sua unidade_demandante.
    - Outros perfis: CRUD completo.
    """
    permission_classes = [PodeVerCustodia]
    filterset_class = DNAFilter
    # Aceita JSON e multipart/form-data (upload de foto)
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = DNA.objects.select_related(
            'perito', 'vestigio__unidade_demandante',
            'created_by', 'updated_by',
        ).order_by('-created_at')

        # EXTERNO vê apenas DNAs dos vestígios da sua unidade
        if _is_externo(self.request.user):
            ud = self.request.user.unidade_demandante
            if ud:
                qs = qs.filter(vestigio__unidade_demandante=ud)
            else:
                return qs.none()

        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return DNAListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return DNACreateSerializer
        return DNADetailSerializer

    def get_permissions(self):
        # EXTERNO não pode editar nem deletar
        if self.action in ('update', 'partial_update', 'destroy'):
            return [PodeCustodiar()]
        # Todos os autenticados podem criar e listar
        return [PodeVerCustodia()]

    def perform_create(self, serializer):
        externo = _is_externo(self.request.user)
        kwargs = {
            'created_by': self.request.user,
            'registrado_por_usuario_externo': externo,
        }
        # Regra do SPR-Custódia: EXTERNO só pode registrar não apenados
        if externo:
            kwargs['situacao'] = DNA.Situacao.NAO_APENADO
        serializer.save(**kwargs)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    @action(detail=True, methods=['get'], url_path='ficha-pdf')
    def ficha_pdf(self, request, pk=None):
        """Gera a Ficha de Coleta de DNA / Perfil Genético em PDF com QR code."""
        dna = self.get_object()
        return gerar_ficha_dna(dna, request)


