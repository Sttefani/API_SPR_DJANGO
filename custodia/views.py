# custodia/views.py

from django.utils import timezone
from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError

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
    UnidadeResumoSerializer,
)
from .permissions import PodeCustodiar, PodeVerCustodia, IsExternoUser, IsCustodianteUser
from .pdf_generator import gerar_ficha_vestigio, gerar_ficha_dna
from .filters import VestigioFilter, DNAFilter
from usuarios.models import User

# Perfis que enxergam apenas os dados da sua própria unidade de lotação
_PERFIS_UNIDADE = {User.Perfil.EXTERNO, User.Perfil.PERITO, User.Perfil.OPERACIONAL}


def _is_externo(user):
    return user.perfil == User.Perfil.EXTERNO


def _filtra_por_unidade(user):
    """True para perfis que só podem ver dados da própria unidade de lotação."""
    return user.perfil in _PERFIS_UNIDADE


def _is_perito_ou_operacional(user):
    return user.perfil in {User.Perfil.PERITO, User.Perfil.OPERACIONAL}


def _qs_filtro_unidade(qs, user, campo_unidade, campo_destino=None):
    """
    Aplica o filtro de visibilidade por unidade ao queryset.

    PERITO / OPERACIONAL: unidade da lotação  OU  atribuídos diretamente ao usuário
    EXTERNO: apenas a unidade da lotação
    """
    ud = user.unidade_demandante
    if not ud:
        return qs.none()

    if _is_perito_ou_operacional(user) and campo_destino:
        return qs.filter(
            Q(**{campo_unidade: ud}) | Q(**{campo_destino: user})
        ).distinct()

    return qs.filter(**{campo_unidade: ud})


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

        # Restrição por perfil:
        # PERITO/OPERACIONAL → unidade da lotação OU atribuídos a eles
        # EXTERNO            → apenas unidade da lotação
        user = self.request.user
        if _filtra_por_unidade(user):
            qs = _qs_filtro_unidade(
                qs, user,
                campo_unidade='unidade_demandante',
                campo_destino='user_destino',
            )

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
        # ---> SEGURANÇA BACKEND: Impede alteração se o vestígio já estiver FINALIZADO
        instance = self.get_object()
        if instance.status == Vestigio.Status.FINALIZADO:
            raise ValidationError(
                {"detail": "Não é permitido alterar um vestígio com status FINALIZADO. É necessário reabri-lo primeiro."}
            )
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
        qs = VestigioMovimentacao.objects.select_related(
            'vestigio', 'unidade_demandante', 'servico_pericial',
            'autoridade', 'user_destino', 'created_by',
        ).order_by('-created_at')

        # PERITO/OPERACIONAL → movimentações da unidade OU de vestígios atribuídos a eles
        # EXTERNO            → apenas movimentações da unidade
        user = self.request.user
        if _filtra_por_unidade(user):
            qs = _qs_filtro_unidade(
                qs, user,
                campo_unidade='vestigio__unidade_demandante',
                campo_destino='vestigio__user_destino',
            )

        return qs

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
        
        # 1. Efetiva o aceite da movimentação técnica
        movimentacao.aceito = True
        movimentacao.data_hora_aceito = timezone.now()
        movimentacao.save()

        # 🚨 O APERTO DE MÃO BRINDADO AQUI:
        vestigio = movimentacao.vestigio
        
        # Transfere a responsabilidade para o perito de destino
        vestigio.user_destino = movimentacao.user_destino
        
        # ATUALIZAÇÃO MACRO: Transfere o vestígio para o novo setor se houver mudança de especialidade
        if movimentacao.servico_pericial:
            vestigio.servico_pericial = movimentacao.servico_pericial

        vestigio.updated_by = request.user
        vestigio.save()

        return Response(VestigioMovimentacaoListSerializer(movimentacao).data)


# ---------------------------------------------------------------------------
# DNA
# ---------------------------------------------------------------------------

class DNAViewSet(viewsets.ModelViewSet):
    """
    Banco de perfis genéticos — listagem e consulta abertas a todos os perfis.

    Regras de cadastro:
    - EXTERNO:           cria apenas NAO_APENADO (situacao forçado, flag externo=True);
                         NÃO pode editar nem deletar.
    - PERITO/OPERACIONAL: cria APENADO e NAO_APENADO; CRUD completo.
    - ADMIN/SUPER_ADMIN/CUSTODIANTE: CRUD completo sem restrição.
    """
    permission_classes = [PodeVerCustodia]
    filterset_class = DNAFilter
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        # Listagem global — sem filtro de unidade (banco nacional de perfis)
        return DNA.objects.select_related(
            'perito', 'vestigio__unidade_demandante',
            'created_by', 'updated_by',
        ).order_by('-created_at')

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


# ---------------------------------------------------------------------------
# Resumo de Custódia — widget embutido nos dashboards dos perfis internos
# ---------------------------------------------------------------------------

class CustodiaResumoView(APIView):
    """
    Dados para o widget de custódia nos dashboards de PERITO, OPERACIONAL,
    ADMINISTRATIVO e SUPER_ADMIN.

    Query params:
      - servico_pericial_id  (todos os perfis — drill-down por área)
      - unidade_demandante_id (admin/super_admin apenas — filtro cruzado de unidade)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs       = Vestigio.objects.all()
        qs_movs  = VestigioMovimentacao.objects.all()
        qs_dnas  = DNA.objects.all()

        # Vestígios e movimentações: filtrados por unidade/atribuição
        # DNAs: banco nacional — sem filtro de unidade para nenhum perfil
        if _filtra_por_unidade(user):
            if not user.unidade_demandante:
                return Response({
                    'vestigios': {'total': 0, 'inicial': 0, 'andamento': 0,
                                  'finalizado': 0, 'biologicos': 0},
                    'dnas_total': 0,
                    'transferencias_pendentes': 0,
                })
            qs      = _qs_filtro_unidade(qs,      user, 'unidade_demandante',           'user_destino')
            qs_movs = _qs_filtro_unidade(qs_movs, user, 'vestigio__unidade_demandante', 'vestigio__user_destino')

        # Filtro por serviço pericial (todos os perfis)
        sp_id = request.query_params.get('servico_pericial_id')
        if sp_id:
            qs      = qs.filter(servico_pericial_id=sp_id)
            qs_movs = qs_movs.filter(vestigio__servico_pericial_id=sp_id)
            qs_dnas = qs_dnas.filter(vestigio__servico_pericial_id=sp_id)

        # Filtro por unidade — permitido apenas a quem já enxerga tudo
        ud_id = request.query_params.get('unidade_demandante_id')
        if ud_id and not _filtra_por_unidade(user):
            qs      = qs.filter(unidade_demandante_id=ud_id)
            qs_movs = qs_movs.filter(vestigio__unidade_demandante_id=ud_id)
            qs_dnas = qs_dnas.filter(vestigio__unidade_demandante_id=ud_id)

        data = {
            'vestigios': {
                'total':      qs.count(),
                'inicial':    qs.filter(status=Vestigio.Status.INICIAL).count(),
                'andamento':  qs.filter(status=Vestigio.Status.ANDAMENTO).count(),
                'finalizado': qs.filter(status=Vestigio.Status.FINALIZADO).count(),
                'biologicos': qs.filter(biologico=True).count(),
            },
            'dnas_total':               qs_dnas.count(),
            'transferencias_pendentes': qs_movs.filter(aceito=False).count(),
        }

        # Breakdown por unidade — somente visão global e sem filtro de unidade ativo
        _is_global = user.perfil in {
            User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN, User.Perfil.CUSTODIANTE
        }
        if _is_global and not ud_id:
            data['vestigios_por_unidade'] = list(
                qs
                .values(
                    'unidade_demandante__id',
                    'unidade_demandante__sigla',
                    'unidade_demandante__nome',
                )
                .annotate(
                    total=Count('id'),
                    ativos=Count('id', filter=~Q(status=Vestigio.Status.FINALIZADO)),
                    biologicos=Count('id', filter=Q(biologico=True)),
                )
                .order_by('-total')
            )

        return Response(data)


# ---------------------------------------------------------------------------
# Dashboard EXTERNO — visão restrita à unidade_demandante do usuário
# ---------------------------------------------------------------------------

class DashboardExternoView(APIView):
    permission_classes = [IsExternoUser]

    def get(self, request):
        user = request.user
        ud = user.unidade_demandante
        if not ud:
            return Response(
                {'detail': 'Usuário externo sem unidade associada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vestigios = Vestigio.objects.filter(unidade_demandante=ud)
        movimentacoes = VestigioMovimentacao.objects.filter(
            vestigio__unidade_demandante=ud
        )
        dnas = DNA.objects.all()   # banco nacional — aberto a todos

        movs_recentes = movimentacoes.select_related(
            'unidade_demandante', 'servico_pericial',
            'autoridade', 'user_destino', 'created_by',
        ).order_by('-created_at')[:5]

        return Response({
            'unidade': UnidadeResumoSerializer(ud).data,
            'vestigios': {
                'total':      vestigios.count(),
                'inicial':    vestigios.filter(status=Vestigio.Status.INICIAL).count(),
                'andamento':  vestigios.filter(status=Vestigio.Status.ANDAMENTO).count(),
                'finalizado': vestigios.filter(status=Vestigio.Status.FINALIZADO).count(),
                'biologicos': vestigios.filter(biologico=True).count(),
            },
            'dnas_total': dnas.count(),
            'movimentacoes_recentes': VestigioMovimentacaoListSerializer(
                movs_recentes, many=True
            ).data,
            'alertas': {
                'transferencias_pendentes': movimentacoes.filter(aceito=False).count(),
            },
        })


# ---------------------------------------------------------------------------
# Dashboard CUSTODIANTE — visão global com agregação por unidade
# ---------------------------------------------------------------------------

class DashboardCustodianteView(APIView):
    permission_classes = [IsCustodianteUser]

    def get(self, request):
        vestigios = Vestigio.objects.all()
        movimentacoes = VestigioMovimentacao.objects.all()
        dnas = DNA.objects.all()

        vestigios_por_unidade = (
            vestigios
            .values(
                'unidade_demandante__id',
                'unidade_demandante__sigla',
                'unidade_demandante__nome',
            )
            .annotate(
                total=Count('id'),
                ativos=Count('id', filter=~Q(status=Vestigio.Status.FINALIZADO)),
                biologicos=Count('id', filter=Q(biologico=True)),
            )
            .order_by('-total')
        )

        movs_recentes = movimentacoes.select_related(
            'vestigio', 'unidade_demandante', 'servico_pericial',
            'autoridade', 'user_destino', 'created_by',
        ).order_by('-created_at')[:10]

        return Response({
            'vestigios': {
                'total':      vestigios.count(),
                'inicial':    vestigios.filter(status=Vestigio.Status.INICIAL).count(),
                'andamento':  vestigios.filter(status=Vestigio.Status.ANDAMENTO).count(),
                'finalizado': vestigios.filter(status=Vestigio.Status.FINALIZADO).count(),
                'biologicos': vestigios.filter(biologico=True).count(),
            },
            'dnas_total': dnas.count(),
            'vestigios_por_unidade': list(vestigios_por_unidade),
            'alertas': {
                'transferencias_pendentes': movimentacoes.filter(aceito=False).count(),
            },
            'movimentacoes_recentes': VestigioMovimentacaoListSerializer(
                movs_recentes, many=True
            ).data,
        })