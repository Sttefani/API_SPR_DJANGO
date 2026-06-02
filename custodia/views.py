# custodia/views.py

from django.utils import timezone
from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend

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
    OcorrenciaResumoSerializer,
)
from .permissions import PodeCustodiar, PodeVerCustodia, IsExternoUser, IsCustodianteUser, IsSuperAdmin
from .pdf_generator import gerar_ficha_vestigio, gerar_ficha_dna
from .filters import VestigioFilter, DNAFilter
from usuarios.models import User
from ocorrencias.models import Ocorrencia

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
    filter_backends   = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class   = VestigioFilter
    search_fields     = ['lacre', 'num_processo_sei', 'ocorrencia', 'descricao', '=id']
    ordering_fields   = ['created_at', 'lacre', 'status']
    ordering          = ['-created_at']

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
        # Deleção restrita a SUPER_ADMIN — o Java original não tinha DELETE em vestígios
        if self.action == 'destroy':
            return [IsSuperAdmin()]
        if self.action in ('create', 'update', 'partial_update',
                            'finalizar', 'reabrir'):
            return [PodeCustodiar()]
        return [PodeVerCustodia()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance  # já carregado pelo update() do DRF — sem double-fetch
        user = self.request.user

        if instance.status == Vestigio.Status.FINALIZADO:
            raise ValidationError(
                {"detail": "Não é permitido alterar um vestígio FINALIZADO. Reabra-o primeiro."}
            )

        # Apenas autor do cadastro ou ADMIN/SUPER_ADMIN pode editar (espelho do VestigioService.update)
        _is_admin = (
            user.perfil in {User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN}
            or user.is_superuser
        )
        if not _is_admin and instance.created_by != user:
            raise ValidationError(
                {"detail": "Apenas o autor do cadastro ou um administrador pode editar este vestígio."}
            )

        serializer.save(updated_by=user)

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    @action(detail=True, methods=['post'], url_path='finalizar')
    def finalizar(self, request, pk=None):
        """
        Finaliza um vestígio com assinatura digital do responsável.

        Regras:
        - Apenas ADMIN, SUPER_ADMIN ou CUSTODIANTE podem finalizar.
        - Deve existir ao menos uma movimentação com a última aceita.
        - Exige motivo_finalizacao (obrigatório para não-repúdio).
        - Exige assinatura digital: email + senha do usuário autenticado.
        - Cria movimentação final copiando a última (BeanUtils.copyProperties do Java).
        """
        vestigio = self.get_object()
        serializer = FinalizarVestigioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        # ── Verificação de perfil ─────────────────────────────────────────
        pode_finalizar = (
            user.perfil in {User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN, User.Perfil.CUSTODIANTE}
            or user.is_superuser
        )
        if not pode_finalizar:
            return Response(
                {'detail': 'Apenas administradores ou custodiantes podem finalizar vestígios.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Assinatura digital (não-repúdio) ──────────────────────────────
        email_assinado = serializer.validated_data['assinatura_email']
        senha_assinada = serializer.validated_data['assinatura_senha']

        if email_assinado.lower().strip() != user.email.lower().strip():
            return Response(
                {'detail': 'O e-mail de assinatura não corresponde ao usuário autenticado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.check_password(senha_assinada):
            return Response(
                {'detail': 'Senha incorreta. Assinatura digital não confirmada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Pré-requisitos de movimentação ────────────────────────────────
        movimentacoes = VestigioMovimentacao.objects.filter(
            vestigio=vestigio
        ).order_by('-created_at')

        if not movimentacoes.exists():
            raise ValidationError(
                {'detail': 'Precisa existir ao menos uma movimentação para finalizar o vestígio.'}
            )

        ultima_mov = movimentacoes.first()
        if not ultima_mov.aceito:
            raise ValidationError(
                {'detail': 'A última movimentação precisa ser aceita antes de finalizar.'}
            )

        # ── Gravar finalização ────────────────────────────────────────────
        motivo = serializer.validated_data['motivo_finalizacao']

        vestigio.status = Vestigio.Status.FINALIZADO
        vestigio.saiu_da_custodia = serializer.validated_data['saiu_da_custodia']
        vestigio.motivo_finalizacao = motivo
        vestigio.updated_by = user
        vestigio.save()

        # Cria movimentação final copiando a última (BeanUtils.copyProperties do Java)
        VestigioMovimentacao.objects.create(
            vestigio=vestigio,
            lacre=ultima_mov.lacre,
            num_processo_sei=ultima_mov.num_processo_sei,
            descricao=motivo,
            unidade_demandante=ultima_mov.unidade_demandante,
            servico_pericial=ultima_mov.servico_pericial,
            autoridade=ultima_mov.autoridade,
            user_destino=ultima_mov.user_destino,
            aceito=True,
            data_hora_aceito=timezone.now(),
            created_by=user,
        )

        return Response(VestigioDetailSerializer(vestigio).data)

    @action(detail=True, methods=['post'], url_path='reabrir')
    def reabrir(self, request, pk=None):
        vestigio = self.get_object()
        vestigio.status = Vestigio.Status.ANDAMENTO
        vestigio.saiu_da_custodia = False
        vestigio.updated_by = request.user
        vestigio.save()
        return Response(VestigioDetailSerializer(vestigio).data)

    @action(detail=True, methods=['patch'], url_path='salvar-ocorrencia')
    def salvar_ocorrencia(self, request, pk=None):
        """
        salvarOcorrencia — espelho de VestigioService.salvarOcorrencia do Java.

        O campo ocorrência é imutável após preenchido: só pode ser gravado
        quando ainda está em branco (ValueValidUtil.isValid no Java).
        """
        vestigio = self.get_object()

        if vestigio.ocorrencia:
            raise ValidationError(
                {'detail': 'A ocorrência já foi preenchida e não pode ser alterada.'}
            )

        ocorrencia = request.data.get('ocorrencia', '').strip()
        if not ocorrencia:
            raise ValidationError({'detail': 'O campo ocorrência é obrigatório.'})

        vestigio.ocorrencia = ocorrencia
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

    @action(detail=True, methods=['get'], url_path='contra-provas')
    def contra_provas(self, request, pk=None):
        """
        Lista todos os vestígios registrados como contraprova deste vestígio.
        Usa o related_name='contra_provas' do FK vestigio_contra_prova.
        """
        vestigio = self.get_object()
        qs = Vestigio.objects.filter(
            vestigio_contra_prova=vestigio
        ).select_related(
            'unidade_demandante', 'servico_pericial',
            'user_destino', 'created_by',
        ).order_by('-created_at')
        return Response(VestigioListSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='vincular-ocorrencia')
    def vincular_ocorrencia(self, request, pk=None):
        """
        Vincula ou desvincula uma Ocorrência a este Vestígio.

        Body: {"ocorrencia_id": <id>, "acao": "add|remove"}

        Regra de cascata: ao vincular, se a Ocorrência tiver
        procedimento_cadastrado, ele é adicionado automaticamente
        a vestigio.procedimentos (mesma lógica do Java).
        """
        vestigio = self.get_object()
        ocorrencia_id = request.data.get('ocorrencia_id')
        acao = request.data.get('acao', 'add')

        if not ocorrencia_id:
            raise ValidationError({'detail': 'ocorrencia_id é obrigatório.'})
        if acao not in ('add', 'remove'):
            raise ValidationError({'detail': 'acao deve ser "add" ou "remove".'})

        try:
            ocorrencia = Ocorrencia.objects.select_related(
                'procedimento_cadastrado'
            ).get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            raise ValidationError({'detail': f'Ocorrência {ocorrencia_id} não encontrada.'})

        if acao == 'add':
            vestigio.ocorrencias_vinculadas.add(ocorrencia)
            # Cascata: vincula o procedimento da ocorrência ao vestígio
            if ocorrencia.procedimento_cadastrado:
                vestigio.procedimentos.add(ocorrencia.procedimento_cadastrado)
            msg = f'Ocorrência {ocorrencia.numero_ocorrencia} vinculada com sucesso.'
        else:
            vestigio.ocorrencias_vinculadas.remove(ocorrencia)
            msg = f'Ocorrência {ocorrencia.numero_ocorrencia} desvinculada.'

        vestigio.updated_by = request.user
        vestigio.save(update_fields=['updated_by', 'updated_at'])

        return Response({
            'message': msg,
            'vestigio': VestigioDetailSerializer(vestigio, context={'request': request}).data,
        })

    @action(detail=True, methods=['get'], url_path='grafo')
    def grafo(self, request, pk=None):
        """
        Retorna a cadeia completa de relações do vestígio:

        vestigio_original (se for contraprova)
            └─ este vestígio
                 ├─ ocorrencias_vinculadas
                 │    └─ procedimento_cadastrado → tipo_procedimento
                 └─ contra_provas (outros vestígios que apontam para este)
        """
        vestigio = self.get_object()

        # Ocorrências vinculadas com cadeia completa
        ocorrencias_data = []
        for oc in vestigio.ocorrencias_vinculadas.select_related(
            'servico_pericial',
            'unidade_demandante',
            'procedimento_cadastrado__tipo_procedimento',
        ).all():
            oc_node = {
                'id': oc.id,
                'numero_ocorrencia': oc.numero_ocorrencia,
                'status': oc.status,
                'status_display': oc.get_status_display(),
                'servico': {
                    'id': oc.servico_pericial_id,
                    'sigla': oc.servico_pericial.sigla,
                    'nome': oc.servico_pericial.nome,
                },
                'unidade': {
                    'id': oc.unidade_demandante_id,
                    'sigla': oc.unidade_demandante.sigla,
                },
                'procedimento': None,
            }
            if oc.procedimento_cadastrado:
                p = oc.procedimento_cadastrado
                oc_node['procedimento'] = {
                    'id': p.id,
                    'numero_completo': f"{p.tipo_procedimento.sigla} {p.numero}/{p.ano}",
                    'numero': p.numero,
                    'ano': p.ano,
                    'tipo': {
                        'id': p.tipo_procedimento_id,
                        'sigla': p.tipo_procedimento.sigla,
                        'nome': p.tipo_procedimento.nome,
                    },
                }
            ocorrencias_data.append(oc_node)

        # Contraprovas
        contra_provas_data = VestigioListSerializer(
            vestigio.contra_provas.select_related(
                'unidade_demandante', 'servico_pericial', 'user_destino'
            ).all(),
            many=True,
        ).data

        return Response({
            'vestigio': VestigioDetailSerializer(vestigio, context={'request': request}).data,
            'vestigio_original': VestigioListSerializer(
                vestigio.vestigio_contra_prova
            ).data if vestigio.vestigio_contra_prova else None,
            'ocorrencias': ocorrencias_data,
            'contra_provas': list(contra_provas_data),
        })

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
        # Deleção restrita a SUPER_ADMIN — movimentações são registros de cadeia de custódia
        if self.action == 'destroy':
            return [IsSuperAdmin()]
        if self.action in ('create', 'update', 'partial_update'):
            return [PodeCustodiar()]
        return [PodeVerCustodia()]

    # -----------------------------------------------------------------------
    # Helpers — espelham VestigioMovimentacaoService do Java
    # -----------------------------------------------------------------------

    @staticmethod
    def _pode_ter_nova_movimentacao(vestigio) -> bool:
        """
        podeTerUmaNovaMovimentacao: retorna True se não há movimentação pendente
        (ou seja, a última já foi aceita ou não existe nenhuma ainda).
        """
        ultima = VestigioMovimentacao.objects.filter(
            vestigio=vestigio
        ).order_by('-created_at').first()
        return ultima is None or ultima.aceito

    @staticmethod
    def _posso_realizar_movimentacao(vestigio, user) -> bool:
        """
        possoRealizarUmaNovaMovimentacao: retorna True se o usuário tem
        permissão para criar nova movimentação neste vestígio.
        Regra: sem movimentações → qualquer um pode,
               caso contrário → deve ser admin, destino ou do mesmo setor.
        """
        if (
            user.perfil in {User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN}
            or user.is_superuser
        ):
            return True

        ultima = VestigioMovimentacao.objects.filter(
            vestigio=vestigio
        ).order_by('-created_at').first()

        if ultima is None:
            return True  # primeira movimentação: qualquer perfil autorizado pode

        if ultima.user_destino_id == user.pk:
            return True  # sou o destinatário da última movimentação

        if ultima.servico_pericial_id:
            return user.servicos_periciais.filter(id=ultima.servico_pericial_id).exists()

        return False

    # -----------------------------------------------------------------------

    def perform_create(self, serializer):
        vestigio = serializer.validated_data['vestigio']
        user = self.request.user

        # Vestígio FINALIZADO não aceita novas movimentações
        if vestigio.status == Vestigio.Status.FINALIZADO:
            raise ValidationError(
                {'detail': 'Vestígio finalizado. Não pode haver novas movimentações.'}
            )

        # Última movimentação deve estar aceita (podeTerUmaNovaMovimentacao)
        if not self._pode_ter_nova_movimentacao(vestigio):
            raise ValidationError(
                {'detail': 'A movimentação anterior precisa ser aceita para dar continuidade.'}
            )

        # Usuário deve ter permissão (possoRealizarUmaNovaMovimentacao)
        if not self._posso_realizar_movimentacao(vestigio, user):
            raise ValidationError(
                {'detail': 'Usuário não tem permissão para cadastrar nova movimentação neste vestígio.'}
            )

        movimentacao = serializer.save(created_by=user)

        # Transição automática INICIAL → ANDAMENTO
        if vestigio.status == Vestigio.Status.INICIAL:
            vestigio.status = Vestigio.Status.ANDAMENTO
            vestigio.updated_by = user
            vestigio.save()

    def perform_update(self, serializer):
        """
        update — espelho de VestigioMovimentacaoService.update do Java.

        Regras:
        - Vestígio FINALIZADO não aceita edição.
        - Movimentação já aceita não pode ser editada (MovimentacaoJaFoiAceitaException).
        - Apenas o criador pode editar; ADMIN/SUPER_ADMIN podem sempre.
        """
        instance = serializer.instance  # já carregado pelo DRF — sem double-fetch
        user = self.request.user

        if instance.vestigio.status == Vestigio.Status.FINALIZADO:
            raise ValidationError(
                {'detail': 'Vestígio finalizado. Não pode haver novas movimentações.'}
            )

        if instance.aceito:
            raise ValidationError(
                {'detail': 'Essa movimentação não pode ser editada pois já foi aceita.'}
            )

        _is_admin = (
            user.perfil in {User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN}
            or user.is_superuser
        )
        if not _is_admin and instance.created_by != user:
            raise ValidationError(
                {'detail': 'Usuário não tem permissão para editar essa movimentação.'}
            )

        serializer.save(updated_by=user)

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    @action(detail=True, methods=['post'], url_path='aceitar')
    def aceitar(self, request, pk=None):
        """
        darAceite — espelho de VestigioMovimentacaoService.darAceite.

        Quem pode aceitar:
        - ADMIN / SUPER_ADMIN / CUSTODIANTE: sempre
        - Mesmo serviço pericial da movimentação
        - EXTERNO da mesma unidade demandante

        Ao aceitar, user_destino da movimentação e do vestígio passam
        a ser o usuário que aceitou (registra quem efetivamente recebeu).
        """
        movimentacao = self.get_object()
        if movimentacao.aceito:
            return Response(
                {'detail': 'Movimentação já foi aceita.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        autorizado = False

        if (
            user.perfil in {User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN, User.Perfil.CUSTODIANTE}
            or user.is_superuser
        ):
            autorizado = True

        elif movimentacao.servico_pericial_id:
            autorizado = user.servicos_periciais.filter(
                id=movimentacao.servico_pericial_id
            ).exists()

        elif _is_externo(user) and movimentacao.unidade_demandante_id and user.unidade_demandante_id:
            autorizado = movimentacao.unidade_demandante_id == user.unidade_demandante_id

        if not autorizado:
            return Response(
                {'detail': 'Usuário não tem permissão para aceitar esta movimentação.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Registra o aceite — quem aceitou vira o responsável (Java: setUserDestino(authUser))
        movimentacao.user_destino = user
        movimentacao.aceito = True
        movimentacao.data_hora_aceito = timezone.now()
        movimentacao.save()

        vestigio = movimentacao.vestigio
        vestigio.user_destino = user  # responsabilidade passa para quem aceitou
        if movimentacao.servico_pericial:
            vestigio.servico_pericial = movimentacao.servico_pericial
        vestigio.updated_by = user
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
    filter_backends   = [DjangoFilterBackend, SearchFilter]
    filterset_class   = DNAFilter
    search_fields     = ['nome', 'cpf', 'codigo_barras']   # ?search= busca nome/CPF/cód. barras
    parser_classes    = [MultiPartParser, FormParser, JSONParser]

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
        # Deleção restrita a SUPER_ADMIN — o Java original não tinha DELETE em DNAs
        if self.action == 'destroy':
            return [IsSuperAdmin()]
        # EXTERNO não pode editar
        if self.action in ('update', 'partial_update'):
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
                    total=Count('id', distinct=True),
                    ativos=Count('id', distinct=True, filter=~Q(status=Vestigio.Status.FINALIZADO)),
                    biologicos=Count('id', distinct=True, filter=Q(biologico=True)),
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
                total=Count('id', distinct=True),
                ativos=Count('id', distinct=True, filter=~Q(status=Vestigio.Status.FINALIZADO)),
                biologicos=Count('id', distinct=True, filter=Q(biologico=True)),
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