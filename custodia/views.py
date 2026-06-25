# custodia/views.py

from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Count, Q, Max
from django.db.models.functions import TruncMonth
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend

from .models import Vestigio, VestigioMovimentacao, DNA, CertidaoRegistro, FichaVestigioRegistro
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
from .permissions import PodeCustodiar, PodeVerCustodia, PodeFinalizar, IsExternoUser, IsCustodianteUser, IsSuperAdmin
from .pdf_generator import (
    gerar_ficha_vestigio, gerar_ficha_dna, gerar_certidao_ausencia_dna,
    gerar_relatorio_vestigios, gerar_relatorio_dnas,
)
from .filters import VestigioFilter, VestigioMovimentacaoFilter, DNAFilter
from usuarios.models import User
from ocorrencias.models import Ocorrencia

# Perfis que enxergam apenas os dados da sua própria unidade de lotação
_PERFIS_UNIDADE = {User.Perfil.EXTERNO, User.Perfil.PERITO, User.Perfil.OPERACIONAL}


def _desc_filtros_vestigios(params) -> str:
    """Monta string legível com os filtros ativos para o cabeçalho do relatório PDF."""
    _status = {'INICIAL': 'Inicial', 'ANDAMENTO': 'Em Andamento', 'FINALIZADO': 'Finalizado'}
    partes = []
    if params.get('status'):
        partes.append(f"Status: {_status.get(params['status'], params['status'])}")
    if params.get('lacre'):
        partes.append(f"Lacre: {params['lacre']}")
    if params.get('num_processo_sei'):
        partes.append(f"SEI: {params['num_processo_sei']}")
    if params.get('ocorrencia'):
        partes.append(f"Ocorrência: {params['ocorrencia']}")
    if params.get('biologico'):
        partes.append(f"Biológico: {'Sim' if params['biologico'].lower() == 'true' else 'Não'}")
    if params.get('conformidade'):
        partes.append(f"Conformidade: {'Sim' if params['conformidade'].lower() == 'true' else 'Não'}")
    if params.get('search'):
        partes.append(f'Busca: "{params["search"]}"')
    if params.get('servico_pericial'):
        try:
            from servicos_periciais.models import ServicoPericial
            sp = ServicoPericial.objects.get(pk=params['servico_pericial'])
            partes.append(f'Serviço: {sp.sigla}')
        except Exception:
            partes.append(f"Serviço ID: {params['servico_pericial']}")
    if params.get('unidade_demandante'):
        try:
            from unidades_demandantes.models import UnidadeDemandante
            ud = UnidadeDemandante.objects.get(pk=params['unidade_demandante'])
            partes.append(f'Unidade: {ud.sigla}')
        except Exception:
            partes.append(f"Unidade ID: {params['unidade_demandante']}")
    return ' | '.join(partes) if partes else 'Todos os registros'


def _desc_filtros_dnas(params) -> str:
    partes = []
    if params.get('nome'):
        partes.append(f"Nome: {params['nome']}")
    if params.get('cpf'):
        partes.append(f"CPF: {params['cpf']}")
    if params.get('situacao'):
        _sit = {'APENADO': 'Apenado', 'NAO_APENADO': 'Não Apenado'}
        partes.append(f"Situação: {_sit.get(params['situacao'], params['situacao'])}")
    if params.get('finalidade_coleta'):
        _fin = {'LEI': 'Lei 12.654/2012', 'DJ': 'Decisão Judicial'}
        partes.append(f"Finalidade: {_fin.get(params['finalidade_coleta'], params['finalidade_coleta'])}")
    if params.get('uf'):
        partes.append(f"UF: {params['uf']}")
    if params.get('data_de'):
        partes.append(f"Coleta a partir de: {params['data_de']}")
    if params.get('data_ate'):
        partes.append(f"Coleta até: {params['data_ate']}")
    if params.get('search'):
        partes.append(f'Busca: "{params["search"]}"')
    if params.get('registrado_por_usuario_externo'):
        partes.append('Registrado por usuário externo')
    return ' | '.join(partes) if partes else 'Todos os registros'


def _is_externo(user):
    return user.perfil == User.Perfil.EXTERNO


def _filtra_por_unidade(user):
    """True para perfis que só podem ver dados da própria unidade de lotação."""
    return user.perfil in _PERFIS_UNIDADE


def _is_perito_ou_operacional(user):
    return user.perfil in {User.Perfil.PERITO, User.Perfil.OPERACIONAL}


def _qs_filtro_unidade(qs, user, campo_unidade, campo_destino=None,
                       campo_criado_por=None, campo_servico=None):
    """
    Aplica o filtro de visibilidade por unidade ao queryset.

    PERITO / OPERACIONAL (nunca retorna qs.none()):
      1. Serviços periciais do usuário (M2M) — critério principal quando campo_servico fornecido
      2. Unidade demandante — se user.unidade_demandante estiver configurada
      3. user_destino = user — atribuição direta
      4. created_by = user  — autor do registro (se campo_criado_por fornecido)

    EXTERNO:
      - Com unidade: apenas unidade_demandante
      - Sem unidade: qs.none()
    """
    ud = user.unidade_demandante

    if _is_perito_ou_operacional(user) and campo_destino:
        # Pessoais — sempre incluídos (nunca retorna vazio por falta de unidade)
        q = Q(**{campo_destino: user})
        if campo_criado_por:
            q |= Q(**{campo_criado_por: user})
        # Serviços periciais onde o usuário trabalha (critério principal para PERITO)
        if campo_servico:
            q |= Q(**{f'{campo_servico}__in': user.servicos_periciais.all()})
        # Unidade demandante (complementar — se configurada)
        if ud:
            q |= Q(**{campo_unidade: ud})
        return qs.filter(q).distinct()

    # EXTERNO — exige unidade configurada
    if not ud:
        return qs.none()
    return qs.filter(**{campo_unidade: ud})


def _qs_movimentacao_por_perfil(qs, user):
    """
    Filtro de visibilidade de MOVIMENTAÇÕES por perfil.

    CRÍTICO — usa os campos DA PRÓPRIA MOVIMENTAÇÃO (servico_pericial /
    unidade_demandante / user_destino), que representam o DESTINO da
    transferência, e NÃO os campos atuais do vestígio. A movimentação já nasce
    gravada com o serviço/unidade de destino; o vestígio só passa a "pertencer"
    a esse destino quando a movimentação é aceita. Filtrar pelos campos do
    vestígio tornaria a transferência PENDENTE invisível ao serviço de destino
    — que então nunca conseguiria dar o aceite (a bola é passada mas o recebedor
    não a vê chegar). Espelha as queries by-servicos-periciais /
    by-unidade-demandante / by-user do VestigioMovimentacaoRepository (Java).

      created_by         → o emissor continua vendo o que enviou
      servico_pericial   → o serviço de destino vê o passe chegando / o que detém
      unidade_demandante → a unidade de destino vê o que chega para ela
      user_destino       → quem recebeu nominalmente continua vendo

    ADMINISTRATIVO / CUSTODIANTE / SUPER_ADMIN não passam por aqui (veem tudo).
    """
    if not _filtra_por_unidade(user):
        return qs

    if _is_externo(user):
        ud = user.unidade_demandante
        if not ud:
            return qs.none()
        return qs.filter(
            Q(unidade_demandante=ud)
            | Q(created_by=user)
            | Q(user_destino=user)
        ).distinct()

    # PERITO / OPERACIONAL
    visivel = (
        Q(created_by=user)
        | Q(user_destino=user)
        | Q(servico_pericial__in=user.servicos_periciais.all())
    )
    if user.unidade_demandante_id:
        visivel |= Q(unidade_demandante=user.unidade_demandante)
    return qs.filter(visivel).distinct()


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
        # PERITO/OPERACIONAL → serviços periciais OU atribuídos OU autor OU unidade
        # EXTERNO            → apenas unidade da lotação
        user = self.request.user
        if _filtra_por_unidade(user):
            qs = _qs_filtro_unidade(
                qs, user,
                campo_unidade='unidade_demandante',
                campo_destino='user_destino',
                campo_criado_por='created_by',
                campo_servico='servico_pericial',
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
        # Reabrir: exclusivo de SUPER_ADMIN — desfaz um encerramento com assinatura formal
        if self.action == 'reabrir':
            return [IsSuperAdmin()]
        # Finalizar: ADMINISTRATIVO, CUSTODIANTE, SUPER_ADMIN (OPERACIONAL e PERITO não encerram)
        if self.action == 'finalizar':
            return [PodeFinalizar()]
        # Editar exige PodeCustodiar (EXTERNO não pode)
        if self.action in ('update', 'partial_update'):
            return [PodeCustodiar()]
        # Criar: EXTERNO também pode (registra vestígios da própria unidade)
        return [PodeVerCustodia()]

    def perform_create(self, serializer):
        kwargs = {'created_by': self.request.user}
        # EXTERNO: força unidade_demandante para a unidade do próprio usuário
        if _is_externo(self.request.user) and self.request.user.unidade_demandante:
            kwargs['unidade_demandante'] = self.request.user.unidade_demandante
        serializer.save(**kwargs)

    def perform_update(self, serializer):
        instance = serializer.instance  # já carregado pelo update() do DRF — sem double-fetch
        user = self.request.user

        # Imutabilidade após movimentação: qualquer movimentação inicia a cadeia de custódia
        # formal — editar depois desacreditaria a integridade probatória do registro.
        if VestigioMovimentacao.objects.filter(vestigio=instance).exists():
            raise ValidationError(
                {"detail": "Vestígio com movimentações não pode ser editado. "
                           "A cadeia de custódia já foi iniciada e o registro é imutável."}
            )

        if instance.status == Vestigio.Status.FINALIZADO:
            raise ValidationError(
                {"detail": "Não é permitido alterar um vestígio FINALIZADO."}
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
        # Atômico (espelha @Transactional do Java): a finalização do vestígio e
        # a movimentação final de encerramento são uma única unidade indivisível.
        # Se qualquer parte falhar, nada é gravado — sem estados intermediários
        # na cadeia de custódia.
        motivo = serializer.validated_data['motivo_finalizacao']

        with transaction.atomic():
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

        return Response(VestigioDetailSerializer(vestigio, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reabrir')
    def reabrir(self, request, pk=None):
        vestigio = self.get_object()
        vestigio.status = Vestigio.Status.ANDAMENTO
        vestigio.saiu_da_custodia = False
        vestigio.updated_by = request.user
        vestigio.save()
        return Response(VestigioDetailSerializer(vestigio, context={'request': request}).data)

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
        return Response(VestigioDetailSerializer(vestigio, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='movimentacoes')
    def movimentacoes(self, request, pk=None):
        vestigio = self.get_object()
        movs = VestigioMovimentacao.objects.filter(
            vestigio=vestigio
        ).select_related(
            'unidade_demandante', 'servico_pericial',
            'autoridade', 'user_destino', 'created_by',
        ).order_by('-created_at')
        serializer = VestigioMovimentacaoListSerializer(movs, many=True, context={'request': request})
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

    @action(detail=True, methods=['post'], url_path='vincular-procedimento',
            permission_classes=[PodeCustodiar])
    def vincular_procedimento(self, request, pk=None):
        """
        Vincula ou desvincula um ProcedimentoCadastrado diretamente a um Vestígio.

        Diferente da cascata automática (que ocorre via ocorrência), esta ação
        permite criar o vínculo M2M direto — útil quando o vestígio pertence a
        um procedimento mas não há ocorrência intermediária.

        Body: { "procedimento_id": <int>, "acao": "add" | "remove" }
        """
        from procedimentos_cadastrados.models import ProcedimentoCadastrado

        vestigio      = self.get_object()
        proc_id       = request.data.get('procedimento_id')
        acao          = request.data.get('acao', 'add')

        if not proc_id:
            raise ValidationError({'detail': 'procedimento_id é obrigatório.'})
        if acao not in ('add', 'remove'):
            raise ValidationError({'detail': 'acao deve ser "add" ou "remove".'})

        try:
            proc = ProcedimentoCadastrado.objects.select_related(
                'tipo_procedimento'
            ).get(pk=proc_id)
        except ProcedimentoCadastrado.DoesNotExist:
            raise ValidationError({'detail': f'Procedimento #{proc_id} não encontrado.'})

        if acao == 'add':
            vestigio.procedimentos.add(proc)
            label = f'{proc.tipo_procedimento.sigla} {proc.numero}/{proc.ano}'
            msg   = f'Procedimento {label} vinculado ao vestígio.'
        else:
            vestigio.procedimentos.remove(proc)
            label = f'{proc.tipo_procedimento.sigla} {proc.numero}/{proc.ano}'
            msg   = f'Procedimento {label} desvinculado do vestígio.'

        vestigio.updated_by = request.user
        vestigio.save(update_fields=['updated_by', 'updated_at'])

        return Response({
            'message': msg,
            'procedimentos': [
                {
                    'id':    p.id,
                    'label': f'{p.tipo_procedimento.sigla} {p.numero}/{p.ano}',
                }
                for p in vestigio.procedimentos.select_related(
                    'tipo_procedimento'
                ).all()
            ],
        })

    @action(detail=True, methods=['get'], url_path='ficha-pdf')
    def ficha_pdf(self, request, pk=None):
        """Gera a Ficha de Acompanhamento do Vestígio em PDF com QR code."""
        vestigio = self.get_object()
        return gerar_ficha_vestigio(vestigio, request)

    @action(detail=False, methods=['get'], url_path='auto-complete')
    def auto_complete(self, request):
        """
        Typeahead de vestígios — espelho de VestigioController.autocomplete() do Java.

        ?valor=<string>  — filtra por lacre, SEI, ocorrência ou descrição
                           se o valor for numérico puro, também filtra por ID
        Retorna no máximo 20 resultados no formato mínimo (id, lacre, ocorrência, status).
        Respeita os filtros de visibilidade por perfil (EXTERNO → apenas sua unidade).
        """
        valor = request.query_params.get('valor', '').strip()
        qs = self.get_queryset()

        if valor:
            from django.db.models import Q as _Q
            filtro = (
                _Q(lacre__icontains=valor)
                | _Q(num_processo_sei__icontains=valor)
                | _Q(ocorrencia__icontains=valor)
                | _Q(descricao__icontains=valor)
            )
            if valor.isdigit():
                filtro |= _Q(id=int(valor))
            qs = qs.filter(filtro)

        qs = qs.only('id', 'lacre', 'ocorrencia', 'ano_ocorrencia', 'status')[:20]
        data = [
            {
                'id': v.id,
                'lacre': v.lacre or '',
                'ocorrencia': v.ocorrencia or '',
                'ano_ocorrencia': v.ano_ocorrencia,
                'status': v.status,
            }
            for v in qs
        ]
        return Response(data)

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

    @action(detail=False, methods=['get'], url_path='relatorio-pdf',
            permission_classes=[PodeVerCustodia])
    def relatorio_pdf(self, request):
        """Relatório em lote PDF (paisagem) com todos os filtros aplicados."""
        qs = self.filter_queryset(self.get_queryset())
        return gerar_relatorio_vestigios(qs, request, _desc_filtros_vestigios(request.query_params))

    @action(detail=False, methods=['get'], url_path='validar-ficha',
            permission_classes=[AllowAny])
    def validar_ficha(self, request):
        """
        Valida a autenticidade de uma Ficha de Acompanhamento do Vestígio (FAV).

        Endpoint público — acessível via QR Code sem autenticação.

        Query param:
          - protocolo  ex.: A1B2-C3D4-E5F6-G7H8  (com ou sem hífens)
        """
        protocolo_raw = request.query_params.get('protocolo', '').strip().upper()
        protocolo = protocolo_raw.replace('-', '')

        if len(protocolo) != 16:
            return Response(
                {'valido': False, 'detail': 'Protocolo inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reg = FichaVestigioRegistro.objects.select_related(
                'vestigio', 'emitido_por'
            ).get(protocolo=protocolo)
        except FichaVestigioRegistro.DoesNotExist:
            return Response(
                {
                    'valido': False,
                    'detail': (
                        'Protocolo não encontrado. '
                        'O documento pode ser inválido, adulterado ou ter sido emitido '
                        'por uma versão anterior do sistema.'
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        protocolo_fmt = f'{protocolo[:4]}-{protocolo[4:8]}-{protocolo[8:12]}-{protocolo[12:16]}'

        # Status atual do vestígio (pode ter mudado desde a emissão)
        status_atual = None
        status_display = None
        conteudo_atual_confere = None
        if reg.vestigio:
            status_atual   = reg.vestigio.status
            status_display = reg.vestigio.get_status_display()
            # Recalcula o digest do estado ATUAL e compara com o gravado na emissão.
            # True  → nada mudou no vestígio desde que esta ficha foi emitida.
            # False → houve movimentações/alterações posteriores à emissão.
            if reg.conteudo_hash:
                from .pdf_generator import _calcular_hash_conteudo
                conteudo_atual_confere = (
                    _calcular_hash_conteudo(reg.vestigio) == reg.conteudo_hash
                )

        return Response({
            'valido':          True,
            'protocolo':       protocolo_fmt,
            'vestigio_id':     reg.vestigio_id,
            'vestigio_lacre':  reg.vestigio_lacre,
            'status_atual':    status_atual,
            'status_display':  status_display,
            # Digest do conteúdo no momento da emissão — deve coincidir com o
            # hash impresso na ficha (prova de integridade contra adulteração).
            'conteudo_hash':           reg.conteudo_hash[:32].upper() if reg.conteudo_hash else None,
            'conteudo_atual_confere':  conteudo_atual_confere,
            'emitido_por':     reg.emitido_por_nome,
            'emitido_em':      reg.emitido_em.strftime('%d/%m/%Y %H:%M'),
        })


# ---------------------------------------------------------------------------
# Movimentação de Vestígio
# ---------------------------------------------------------------------------

class VestigioMovimentacaoViewSet(viewsets.ModelViewSet):
    permission_classes  = [PodeVerCustodia]
    filter_backends     = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class     = VestigioMovimentacaoFilter
    search_fields       = ['lacre', 'num_processo_sei', 'descricao', 'vestigio__lacre']
    ordering_fields     = ['created_at', 'data_hora_aceito']
    ordering            = ['-created_at']

    def get_queryset(self):
        qs = VestigioMovimentacao.objects.select_related(
            'vestigio', 'unidade_demandante', 'servico_pericial',
            'autoridade', 'user_destino', 'created_by',
        ).order_by('-created_at')

        user = self.request.user

        # Visibilidade por perfil — pelos campos da própria movimentação (destino
        # do passe), não pelos campos atuais do vestígio. Ver _qs_movimentacao_por_perfil.
        qs = _qs_movimentacao_por_perfil(qs, user)

        # Filtro especial: ?aguardando_meu_aceite=true
        # Retorna apenas movimentações pendentes que o usuário atual pode aceitar,
        # replicando a lógica de get_pode_aceitar() do serializer no lado do banco.
        if self.request.query_params.get('aguardando_meu_aceite') == 'true':
            qs = qs.filter(aceito=False)
            if not (user.is_superuser or user.perfil == User.Perfil.SUPER_ADMIN):
                if user.perfil == User.Perfil.CUSTODIANTE:
                    qs = qs.exclude(created_by=user)
                elif user.perfil in {
                    User.Perfil.PERITO, User.Perfil.OPERACIONAL, User.Perfil.ADMINISTRATIVO
                }:
                    # ADMINISTRATIVO recebe por lotação, então sua caixa de aceite
                    # é filtrada por serviço pericial, igual a PERITO/OPERACIONAL.
                    servicos_ids = user.servicos_periciais.values_list('id', flat=True)
                    qs = qs.filter(
                        Q(servico_pericial__in=servicos_ids) | Q(user_destino=user)
                    )
                elif user.perfil == User.Perfil.EXTERNO and user.unidade_demandante_id:
                    qs = qs.filter(unidade_demandante=user.unidade_demandante)
                else:
                    qs = qs.none()

        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return VestigioMovimentacaoCreateSerializer
        return VestigioMovimentacaoListSerializer

    def get_permissions(self):
        # Deleção restrita a SUPER_ADMIN — movimentações são registros de cadeia de custódia
        if self.action == 'destroy':
            return [IsSuperAdmin()]
        if self.action in ('update', 'partial_update'):
            return [PodeCustodiar()]
        # create: EXTERNO também pode (envio inicial à custódia)
        if self.action == 'create':
            return [PodeVerCustodia()]
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

        # EXTERNO: validações adicionais para o envio inicial à custódia
        if _is_externo(user):
            if vestigio.created_by_id != user.pk:
                raise ValidationError(
                    {'detail': 'Usuário externo só pode movimentar vestígios que cadastrou.'}
                )
            if not serializer.validated_data.get('servico_pericial'):
                raise ValidationError(
                    {'detail': 'Usuário externo deve informar o serviço pericial de destino.'}
                )

        # Atômico: registrar a movimentação e a transição INICIAL → ANDAMENTO
        # do vestígio são indivisíveis — não pode existir movimentação sem o
        # status do vestígio refletir que a cadeia de custódia foi iniciada.
        with transaction.atomic():
            movimentacao = serializer.save(created_by=user)

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

        # Override global de aceite: SUPER_ADMIN e CUSTODIANTE.
        # ADMINISTRATIVO NÃO tem override — só recebe se estiver lotado no
        # serviço pericial de destino (mesma regra de PERITO/OPERACIONAL).
        if (
            user.perfil in {User.Perfil.SUPER_ADMIN, User.Perfil.CUSTODIANTE}
            or user.is_superuser
        ):
            autorizado = True

        elif movimentacao.servico_pericial_id:
            # PERITO / OPERACIONAL / ADMINISTRATIVO: só se lotado no serviço de destino
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

        # ── Aceite atômico com trava pessimista ───────────────────────────────
        # Registrar o recebimento na movimentação e transferir a posse no vestígio
        # são indivisíveis. select_for_update serializa o acesso à linha e impede
        # aceite duplo sob concorrência (dois servidores confirmando ao mesmo tempo)
        # — supera o Java, que tinha @Transactional mas não travava a linha.
        with transaction.atomic():
            # NÃO usar select_related aqui: servico_pericial/unidade são FKs
            # nuláveis e gerariam LEFT OUTER JOIN — o PostgreSQL proíbe
            # SELECT ... FOR UPDATE no lado nulável de um outer join. Travamos
            # apenas a linha da própria movimentação (tabela base).
            mov = (
                VestigioMovimentacao.objects
                .select_for_update()
                .get(pk=movimentacao.pk)
            )
            # Re-checagem sob trava: se outra requisição aceitou primeiro, aborta.
            if mov.aceito:
                return Response(
                    {'detail': 'Movimentação já foi aceita.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Quem aceitou vira o responsável (Java: setUserDestino(authUser))
            mov.user_destino = user
            mov.aceito = True
            mov.data_hora_aceito = timezone.now()
            mov.save()

            vestigio = Vestigio.objects.select_for_update().get(pk=mov.vestigio_id)
            vestigio.user_destino = user  # responsabilidade passa para quem aceitou
            if mov.servico_pericial_id:
                # usa o FK por _id (sem carregar o objeto) — evita join e query extra
                vestigio.servico_pericial_id = mov.servico_pericial_id
            vestigio.updated_by = user
            vestigio.save()

        return Response(
            VestigioMovimentacaoListSerializer(mov, context={'request': request}).data
        )


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

    @action(detail=False, methods=['get'], url_path='certidao-ausencia',
            permission_classes=[PodeVerCustodia])
    def certidao_ausencia(self, request):
        """
        Certidão de Ausência de Registro de Perfil Genético.

        Emitida apenas quando a consulta ao banco de DNA retorna zero resultados.
        Se o DNA for encontrado, retorna 400 com o ID do registro existente.

        Query params (ao menos um obrigatório):
          - nome  (busca por icontains, ignora maiúsculas)
          - cpf   (busca exata após remover pontuação)
          - rg    (busca por icontains, ignora maiúsculas)
        """
        nome = request.query_params.get('nome', '').strip()
        cpf  = request.query_params.get('cpf',  '').strip()
        rg   = request.query_params.get('rg',   '').strip()

        if not nome and not cpf and not rg:
            return Response(
                {'detail': 'Informe ao menos nome, CPF ou RG para realizar a consulta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = DNA.objects.all()
        if cpf:
            cpf_limpo = cpf.replace('.', '').replace('-', '').replace(' ', '')
            qs = qs.filter(cpf__icontains=cpf_limpo)
        if nome:
            qs = qs.filter(nome__icontains=nome.upper())
        if rg:
            qs = qs.filter(rg__icontains=rg.upper())

        if qs.exists():
            dna = qs.first()
            return Response(
                {
                    'detail': (
                        'Registro de perfil genético encontrado para os dados informados. '
                        'Não é possível emitir certidão de ausência.'
                    ),
                    'dna_id': dna.id,
                    'dna_nome': dna.nome,
                },
                status=status.HTTP_409_CONFLICT,
            )

        return gerar_certidao_ausencia_dna(request, nome=nome, cpf=cpf, rg=rg)

    @action(detail=False, methods=['get'], url_path='relatorio-pdf',
            permission_classes=[PodeVerCustodia])
    def relatorio_pdf(self, request):
        """Relatório em lote PDF (paisagem) com todos os filtros aplicados."""
        qs = self.filter_queryset(self.get_queryset())
        return gerar_relatorio_dnas(qs, request, _desc_filtros_dnas(request.query_params))

    @action(detail=False, methods=['get'], url_path='validar-certidao',
            permission_classes=[AllowAny])
    def validar_certidao(self, request):
        """
        Valida a autenticidade de uma Certidão ou Comprovante de Ausência de DNA.

        Endpoint público — acessível via QR Code sem autenticação.

        Query param:
          - protocolo  ex.: A1B2-C3D4-E5F6-G7H8  (com ou sem hífens)
        """
        protocolo_raw = request.query_params.get('protocolo', '').strip().upper()
        protocolo = protocolo_raw.replace('-', '')

        if len(protocolo) != 16:
            return Response(
                {'valido': False, 'detail': 'Protocolo inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reg = CertidaoRegistro.objects.select_related('emitido_por').get(protocolo=protocolo)
        except CertidaoRegistro.DoesNotExist:
            return Response(
                {
                    'valido': False,
                    'detail': (
                        'Protocolo não encontrado. '
                        'O documento pode ser inválido, adulterado ou ter sido emitido '
                        'por uma versão anterior do sistema.'
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        protocolo_fmt = f'{protocolo[:4]}-{protocolo[4:8]}-{protocolo[8:12]}-{protocolo[12:16]}'
        return Response({
            'valido':           True,
            'protocolo':        protocolo_fmt,
            'tipo':             reg.tipo,
            'tipo_display':     reg.get_tipo_display(),
            'nome_consultado':  reg.nome_consultado,
            'cpf_consultado':   reg.cpf_consultado,
            'rg_consultado':    reg.rg_consultado,
            'emitido_por':      reg.emitido_por_nome,
            'emitido_em':       reg.emitido_em.strftime('%d/%m/%Y %H:%M'),
        })


# ---------------------------------------------------------------------------
# Teia de Relações — grafo visual entre Vestígios, Ocorrências e Procedimentos
# ---------------------------------------------------------------------------

class GrafoRelacoesView(APIView):
    """
    Retorna nodes + edges prontos para Cytoscape.js.

    Perfis autorizados: PERITO, OPERACIONAL, ADMINISTRATIVO, SUPER_ADMIN.

    Query params:
      - tipo: 'vestigio' | 'ocorrencia' | 'procedimento'
      - id:   PK da entidade focal
    """
    permission_classes = [IsAuthenticated]

    _PERFIS_PERMITIDOS = {
        User.Perfil.PERITO,
        User.Perfil.OPERACIONAL,
        User.Perfil.ADMINISTRATIVO,
        User.Perfil.SUPER_ADMIN,
    }

    def get(self, request):
        user = request.user
        if user.perfil not in self._PERFIS_PERMITIDOS and not user.is_superuser:
            return Response(
                {'detail': 'Acesso restrito a peritos, operacionais e administradores.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        tipo  = request.query_params.get('tipo', '').strip().lower()
        id_raw = request.query_params.get('id',  '').strip()

        if not tipo or not id_raw:
            return Response(
                {'detail': 'Parâmetros "tipo" e "id" são obrigatórios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            pk = int(id_raw)
        except ValueError:
            return Response(
                {'detail': '"id" deve ser inteiro.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if tipo == 'vestigio':
            return self._grafo_vestigio(pk)
        if tipo == 'ocorrencia':
            return self._grafo_ocorrencia(pk)
        if tipo == 'procedimento':
            return self._grafo_procedimento(pk)

        return Response(
            {'detail': 'Tipo inválido. Use: vestigio, ocorrencia ou procedimento.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Builders de nós ──────────────────────────────────────────────────────

    @staticmethod
    def _nv(v, focal=False, subtipo='vestigio', acessivel=True):
        label = f'{v.lacre}\n#{v.id}' if v.lacre else f'#{v.id}'
        # Procedimentos diretamente vinculados ao vestígio (M2M direto, sem ocorrência)
        procs_diretos = [
            {'id': p.id, 'label': f'{p.tipo_procedimento.sigla} {p.numero}/{p.ano}'}
            for p in v.procedimentos.select_related('tipo_procedimento').all()
        ]
        return {'data': {
            'id':                  f'vest_{v.id}',
            'tipo':                subtipo,
            'label':               label,
            'focal':               focal,
            'status':              v.status,
            'status_display':      v.get_status_display(),
            'unidade':             v.unidade_demandante.sigla if v.unidade_demandante else '—',
            'servico':             v.servico_pericial.sigla   if v.servico_pericial   else '—',
            'responsavel':         v.user_destino.nome_completo if v.user_destino else '—',
            'biologico':           v.biologico,
            'url':                 f'vestigio:{v.id}',
            'procedimentos_diretos': procs_diretos,
            'acessivel':           acessivel,
        }}

    @staticmethod
    def _no(oc, focal=False):
        return {'data': {
            'id':             f'oc_{oc.id}',
            'tipo':           'ocorrencia',
            'label':          oc.numero_ocorrencia,
            'focal':          focal,
            'status':         oc.status,
            'status_display': oc.get_status_display(),
            'perito':         oc.perito_atribuido.nome_completo if oc.perito_atribuido else 'Não atribuído',
            'servico':        oc.servico_pericial.sigla   if oc.servico_pericial   else '—',
            'unidade':        oc.unidade_demandante.sigla if oc.unidade_demandante else '—',
            'url':            f'ocorrencia:{oc.id}',
        }}

    @staticmethod
    def _np(proc, focal=False):
        label = f'{proc.tipo_procedimento.sigla} {proc.numero}/{proc.ano}'
        return {'data': {
            'id':        f'proc_{proc.id}',
            'tipo':      'procedimento',
            'label':     label,
            'focal':     focal,
            'tipo_nome': proc.tipo_procedimento.nome,
            'numero':    proc.numero,
            'ano':       proc.ano,
            'url':       f'procedimento:{proc.id}',
        }}

    @staticmethod
    def _edge(src, tgt, tipo):
        return {'data': {'id': f'e_{src}_{tgt}', 'source': src, 'target': tgt, 'tipo': tipo}}

    @staticmethod
    def _nm(mov, index):
        """Nó de movimentação — para a cadeia de custódia cronológica."""
        destino  = mov.user_destino.nome_completo.split()[0] if mov.user_destino else '?'
        data_fmt = mov.created_at.strftime('%d/%m/%y') if mov.created_at else '?'
        subtipo  = 'movimentacao_aceita' if mov.aceito else 'movimentacao_pendente'
        return {'data': {
            'id':           f'mov_{mov.id}',
            'tipo':         subtipo,
            'label':        f'Mov #{index}\n{destino} · {data_fmt}',
            'focal':        False,
            'aceito':       mov.aceito,
            'criado_por':   mov.created_by.nome_completo  if mov.created_by  else '—',
            'destinatario': mov.user_destino.nome_completo if mov.user_destino else '—',
            'unidade':      mov.unidade_demandante.sigla   if mov.unidade_demandante else '—',
            'servico':      mov.servico_pericial.sigla     if mov.servico_pericial   else '—',
            'descricao':    mov.descricao or '',
            'data_envio':   mov.created_at.strftime('%d/%m/%Y %H:%M')       if mov.created_at       else '—',
            'data_aceite':  mov.data_hora_aceito.strftime('%d/%m/%Y %H:%M') if mov.data_hora_aceito else None,
            'url':          f'movimentacao:{mov.id}',
        }}

    @staticmethod
    def _nd(dna):
        """Nó de DNA (perfil genético)."""
        nome_curto = dna.nome[:18] + '…' if len(dna.nome) > 18 else dna.nome
        return {'data': {
            'id':              f'dna_{dna.id}',
            'tipo':            'dna',
            'label':           f'{nome_curto}\n{dna.get_situacao_display()}',
            'focal':           False,
            'nome':            dna.nome,
            'cpf':             dna.cpf   or '—',
            'rg':              dna.rg    or '—',
            'situacao':        dna.situacao,
            'situacao_display': dna.get_situacao_display(),
            'finalidade':      dna.get_finalidade_coleta_display(),
            'perito':          dna.perito.nome_completo if dna.perito else '—',
            'data_coleta':     dna.data_da_coleta.strftime('%d/%m/%Y') if dna.data_da_coleta else '—',
            'url':             f'dna:{dna.id}',
        }}

    # ── helpers reutilizáveis ──────────────────────────────────────────────────

    def _get_ids_acessiveis(self):
        """
        Retorna o conjunto de IDs de vestígios que o usuário corrente pode abrir
        (mesma lógica do VestigioViewSet.get_queryset).
        ADMINISTRATIVO e SUPER_ADMIN têm acesso total → retorna None.
        """
        user = self.request.user
        if user.perfil in {User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN} or user.is_superuser:
            return None
        qs = _qs_filtro_unidade(
            Vestigio.objects.only('id'), user,
            campo_unidade='unidade_demandante',
            campo_destino='user_destino',
            campo_criado_por='created_by',
            campo_servico='servico_pericial',
        )
        return set(qs.values_list('id', flat=True))

    def _adicionar_dnas_vestigio(self, v, nodes, edges):
        """Adiciona nós DNA ligados ao vestígio e retorna os IDs já adicionados."""
        for dna in v.dnas.select_related('perito').all():
            nodes.append(self._nd(dna))
            edges.append(self._edge(f'vest_{v.id}', f'dna_{dna.id}', 'vestigio_dna'))

    # ── Grafo a partir de um Vestígio ─────────────────────────────────────────

    def _grafo_vestigio(self, pk):
        com_movimentacoes = self.request.query_params.get('incluir_movimentacoes') == '1'

        try:
            v = Vestigio.objects.select_related(
                'unidade_demandante', 'servico_pericial', 'user_destino',
                'vestigio_contra_prova',
            ).get(pk=pk)
        except Vestigio.DoesNotExist:
            return Response({'detail': 'Vestígio não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        ids_acessiveis = self._get_ids_acessiveis()
        pode_ver = lambda vid: ids_acessiveis is None or vid in ids_acessiveis

        nodes, edges, seen_procs = [], [], set()
        nodes.append(self._nv(v, focal=True))  # focal: sempre acessível (usuário abriu)

        # ── Ocorrências + procedimentos ────────────────────────────────────────
        for oc in v.ocorrencias_vinculadas.select_related(
            'perito_atribuido', 'servico_pericial', 'unidade_demandante',
            'procedimento_cadastrado__tipo_procedimento',
        ).all():
            nodes.append(self._no(oc))
            edges.append(self._edge(f'oc_{oc.id}', f'vest_{v.id}', 'oc_vestigio'))
            if oc.procedimento_cadastrado:
                p = oc.procedimento_cadastrado
                if p.id not in seen_procs:
                    nodes.append(self._np(p))
                    seen_procs.add(p.id)
                edges.append(self._edge(f'proc_{p.id}', f'oc_{oc.id}', 'proc_ocorrencia'))

        for p in v.procedimentos.select_related('tipo_procedimento').all():
            if p.id not in seen_procs:
                nodes.append(self._np(p))
                seen_procs.add(p.id)
                edges.append(self._edge(f'proc_{p.id}', f'vest_{v.id}', 'proc_vestigio'))

        # ── Contraprovas ───────────────────────────────────────────────────────
        if v.vestigio_contra_prova:
            orig = v.vestigio_contra_prova
            nodes.append(self._nv(orig, acessivel=pode_ver(orig.id)))
            edges.append(self._edge(f'vest_{orig.id}', f'vest_{v.id}', 'contraprova'))

        for cp in Vestigio.objects.filter(
            vestigio_contra_prova=v
        ).select_related('unidade_demandante', 'servico_pericial', 'user_destino'):
            nodes.append(self._nv(cp, subtipo='contraprova', acessivel=pode_ver(cp.id)))
            edges.append(self._edge(f'vest_{v.id}', f'vest_{cp.id}', 'contraprova'))

        # ── DNAs vinculados ao vestígio ────────────────────────────────────────
        self._adicionar_dnas_vestigio(v, nodes, edges)

        # ── Cadeia de custódia (toggle) ────────────────────────────────────────
        if com_movimentacoes:
            movs = VestigioMovimentacao.objects.filter(
                vestigio=v
            ).select_related(
                'unidade_demandante', 'servico_pericial', 'user_destino', 'created_by'
            ).order_by('created_at')

            prev_id = f'vest_{v.id}'
            for i, mov in enumerate(movs, start=1):
                nodes.append(self._nm(mov, i))
                edges.append(self._edge(prev_id, f'mov_{mov.id}', 'movimentacao'))
                prev_id = f'mov_{mov.id}'

        return Response({
            'focal_id':    f'vest_{v.id}',
            'focal_label': v.lacre or f'Vestígio #{v.id}',
            'focal_tipo':  'vestigio',
            'nodes': nodes,
            'edges': edges,
        })

    # ── Grafo a partir de uma Ocorrência ──────────────────────────────────────

    def _grafo_ocorrencia(self, pk):
        from ocorrencias.models import Ocorrencia
        try:
            oc = Ocorrencia.objects.select_related(
                'perito_atribuido', 'servico_pericial', 'unidade_demandante',
                'procedimento_cadastrado__tipo_procedimento',
            ).get(pk=pk)
        except Ocorrencia.DoesNotExist:
            return Response({'detail': 'Ocorrência não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        ids_acessiveis = self._get_ids_acessiveis()
        pode_ver = lambda vid: ids_acessiveis is None or vid in ids_acessiveis

        nodes, edges = [], []
        nodes.append(self._no(oc, focal=True))

        if oc.procedimento_cadastrado:
            p = oc.procedimento_cadastrado
            nodes.append(self._np(p))
            edges.append(self._edge(f'proc_{p.id}', f'oc_{oc.id}', 'proc_ocorrencia'))

            for outra in Ocorrencia.objects.filter(
                procedimento_cadastrado=p
            ).exclude(pk=oc.pk).select_related(
                'perito_atribuido', 'servico_pericial', 'unidade_demandante',
            ):
                nodes.append(self._no(outra))
                edges.append(self._edge(f'proc_{p.id}', f'oc_{outra.id}', 'proc_ocorrencia'))

        for v in oc.vestigios.select_related(
            'unidade_demandante', 'servico_pericial', 'user_destino',
        ).all():
            nodes.append(self._nv(v, acessivel=pode_ver(v.id)))
            edges.append(self._edge(f'oc_{oc.id}', f'vest_{v.id}', 'oc_vestigio'))
            self._adicionar_dnas_vestigio(v, nodes, edges)

        return Response({
            'focal_id':    f'oc_{oc.id}',
            'focal_label': oc.numero_ocorrencia,
            'focal_tipo':  'ocorrencia',
            'nodes': nodes,
            'edges': edges,
        })

    # ── Grafo a partir de um Procedimento ─────────────────────────────────────

    def _grafo_procedimento(self, pk):
        from procedimentos_cadastrados.models import ProcedimentoCadastrado
        from ocorrencias.models import Ocorrencia as OcorrenciaModel
        try:
            proc = ProcedimentoCadastrado.objects.select_related('tipo_procedimento').get(pk=pk)
        except ProcedimentoCadastrado.DoesNotExist:
            return Response({'detail': 'Procedimento não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        ids_acessiveis = self._get_ids_acessiveis()
        pode_ver = lambda vid: ids_acessiveis is None or vid in ids_acessiveis

        nodes, edges, seen_vest = [], [], set()
        nodes.append(self._np(proc, focal=True))

        for oc in OcorrenciaModel.objects.filter(
            procedimento_cadastrado=proc
        ).select_related('perito_atribuido', 'servico_pericial', 'unidade_demandante'):
            nodes.append(self._no(oc))
            edges.append(self._edge(f'proc_{proc.id}', f'oc_{oc.id}', 'proc_ocorrencia'))

            for v in oc.vestigios.select_related(
                'unidade_demandante', 'servico_pericial', 'user_destino',
            ).all():
                if v.id not in seen_vest:
                    nodes.append(self._nv(v, acessivel=pode_ver(v.id)))
                    seen_vest.add(v.id)
                edges.append(self._edge(f'oc_{oc.id}', f'vest_{v.id}', 'oc_vestigio'))

        for v in Vestigio.objects.filter(
            procedimentos=proc
        ).select_related('unidade_demandante', 'servico_pericial', 'user_destino'):
            if v.id not in seen_vest:
                nodes.append(self._nv(v, acessivel=pode_ver(v.id)))
                seen_vest.add(v.id)
                self._adicionar_dnas_vestigio(v, nodes, edges)
                edges.append(self._edge(f'proc_{proc.id}', f'vest_{v.id}', 'proc_vestigio'))

        return Response({
            'focal_id':    f'proc_{proc.id}',
            'focal_label': f'{proc.tipo_procedimento.sigla} {proc.numero}/{proc.ano}',
            'focal_tipo':  'procedimento',
            'nodes': nodes,
            'edges': edges,
        })


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

        # Vestígios e movimentações: filtrados por perfil (mesma lógica das
        # listagens, para o widget bater com o que o usuário realmente vê).
        # DNAs: banco nacional — sem filtro de unidade para nenhum perfil.
        #
        # NÃO há atalho "sem unidade → zeros": PERITO/OPERACIONAL enxergam por
        # serviço pericial e por autoria (created_by), e tipicamente não têm
        # unidade_demandante preenchida — zerar aqui esvaziaria o widget deles.
        if _filtra_por_unidade(user):
            qs = _qs_filtro_unidade(
                qs, user,
                campo_unidade='unidade_demandante',
                campo_destino='user_destino',
                campo_criado_por='created_by',
                campo_servico='servico_pericial',
            )
            qs_movs = _qs_movimentacao_por_perfil(qs_movs, user)

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

        limite_parado = timezone.now() - timedelta(days=30)
        vestigios_parados = vestigios.filter(
            status__in=[Vestigio.Status.INICIAL, Vestigio.Status.ANDAMENTO],
            updated_at__lt=limite_parado,
        ).count()

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
                'vestigios_parados': vestigios_parados,
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


# ---------------------------------------------------------------------------
# Analytics de Custódia — raio X completo (sessão 9)
# ---------------------------------------------------------------------------

class AnalyticsCustodiaView(APIView):
    """
    Dashboard analytics completo do módulo de custódia.

    Retorna KPIs, cards de status com drill-down, gráficos,
    matriz serviço × status e alertas operacionais.

    Filtros: data_inicio, data_fim, servico_pericial_id
    Permissão: PodeCustodiar (todos exceto EXTERNO)
    """
    permission_classes = [PodeCustodiar]

    def get(self, request):
        def safe_int(val):
            try:
                return int(val) if val not in ['null', '', None] else None
            except Exception:
                return None

        data_inicio   = request.GET.get('data_inicio')
        data_fim      = request.GET.get('data_fim')
        servico_id    = safe_int(request.GET.get('servico_pericial_id'))

        # -------------------------------------------------------------------
        # Querysets base com filtros
        # -------------------------------------------------------------------
        # -------------------------------------------------------------------
        # Escopo de visibilidade por perfil + filtros (serviço, data)
        # -------------------------------------------------------------------
        # CUSTODIANTE / ADMINISTRATIVO / SUPER_ADMIN → visão global.
        # PERITO / OPERACIONAL → apenas o(s) serviço(s) em que estão lotados.
        # Movimentações e DNAs herdam o serviço pelo vestígio vinculado.
        user = request.user
        ver_tudo = (
            user.perfil in {
                User.Perfil.CUSTODIANTE, User.Perfil.ADMINISTRATIVO, User.Perfil.SUPER_ADMIN
            }
            or user.is_superuser
        )
        servicos_ids = None if ver_tudo else list(
            user.servicos_periciais.values_list('id', flat=True)
        )

        # Bases já com escopo de perfil + filtro de serviço (sem janela de data)
        qs_base     = Vestigio.objects.all()
        qs_dna_base = DNA.objects.all()
        qs_mov_base = VestigioMovimentacao.objects.all()

        if servicos_ids is not None:
            qs_base     = qs_base.filter(servico_pericial_id__in=servicos_ids)
            qs_dna_base = qs_dna_base.filter(vestigio__servico_pericial_id__in=servicos_ids)
            qs_mov_base = qs_mov_base.filter(vestigio__servico_pericial_id__in=servicos_ids)
        if servico_id:
            qs_base     = qs_base.filter(servico_pericial_id=servico_id)
            qs_dna_base = qs_dna_base.filter(vestigio__servico_pericial_id=servico_id)
            qs_mov_base = qs_mov_base.filter(vestigio__servico_pericial_id=servico_id)

        # Janela de data (created_at) — para os painéis de volume/período
        qs     = qs_base
        qs_dna = qs_dna_base
        qs_mov = qs_mov_base
        if data_inicio:
            qs     = qs.filter(created_at__date__gte=data_inicio)
            qs_dna = qs_dna.filter(created_at__date__gte=data_inicio)
            qs_mov = qs_mov.filter(created_at__date__gte=data_inicio)
        if data_fim:
            qs     = qs.filter(created_at__date__lte=data_fim)
            qs_dna = qs_dna.filter(created_at__date__lte=data_fim)
            qs_mov = qs_mov.filter(created_at__date__lte=data_fim)

        total = qs.count() or 1  # evitar divisão por zero

        # -------------------------------------------------------------------
        # KPIs (todos respeitam escopo de perfil + filtros)
        # -------------------------------------------------------------------
        agora = timezone.now()
        total_vestigios    = qs.count()
        vestigios_ativos   = qs.filter(status__in=[Vestigio.Status.INICIAL, Vestigio.Status.ANDAMENTO]).count()
        # "Aguardando aceite" e "Finalizados no mês" são fotografias do estado
        # atual: escopadas por perfil/serviço, mas sem a janela de data.
        aguardando_aceite  = qs_mov_base.filter(aceito=False).count()
        total_dnas         = qs_dna.count()
        biologicos_ativos  = qs.filter(biologico=True, status__in=[Vestigio.Status.INICIAL, Vestigio.Status.ANDAMENTO]).count()
        saiu_custodia      = qs.filter(status=Vestigio.Status.FINALIZADO, saiu_da_custodia=True).count()

        finalizados_mes = qs_base.filter(
            status=Vestigio.Status.FINALIZADO,
            updated_at__year=agora.year,
            updated_at__month=agora.month,
        ).count()

        # -------------------------------------------------------------------
        # Cards de status com drill-down por serviço pericial
        # -------------------------------------------------------------------
        cards_status = []
        for s_val, label, icon in [
            (Vestigio.Status.INICIAL,    'Iniciais',      'bi-box-seam'),
            (Vestigio.Status.ANDAMENTO,  'Em Andamento',  'bi-arrow-left-right'),
            (Vestigio.Status.FINALIZADO, 'Finalizados',   'bi-check-circle-fill'),
        ]:
            qtd = qs.filter(status=s_val).count()
            por_servico = (
                qs.filter(status=s_val)
                .values('servico_pericial__sigla', 'servico_pericial__nome')
                .annotate(quantidade=Count('id'))
                .order_by('-quantidade')
            )
            cards_status.append({
                'status':     s_val,
                'label':      label,
                'icon':       icon,
                'quantidade': qtd,
                'percentual': round(qtd / total * 100, 1),
                'por_servico': [
                    {
                        'sigla':      i['servico_pericial__sigla'] or '?',
                        'nome':       i['servico_pericial__nome'] or 'N/I',
                        'quantidade': i['quantidade'],
                    }
                    for i in por_servico
                ],
            })

        # -------------------------------------------------------------------
        # Gráficos
        # -------------------------------------------------------------------

        # Vestígios por serviço pericial
        por_servico = (
            qs.values('servico_pericial__sigla', 'servico_pericial__nome')
            .annotate(quantidade=Count('id'))
            .order_by('-quantidade')[:10]
        )

        # Vestígios por unidade demandante
        por_unidade = (
            qs.values('unidade_demandante__sigla', 'unidade_demandante__nome')
            .annotate(quantidade=Count('id'))
            .order_by('-quantidade')[:10]
        )

        # Evolução mensal — cadastros
        por_mes_cadastro = (
            qs.filter(created_at__isnull=False)
            .annotate(mes=TruncMonth('created_at'))
            .values('mes')
            .annotate(quantidade=Count('id'))
            .order_by('mes')
        )

        # Evolução mensal — finalizações (mesmo escopo de perfil/serviço; janela por updated_at)
        qs_final = qs_base.filter(status=Vestigio.Status.FINALIZADO, updated_at__isnull=False)
        if data_inicio:
            qs_final = qs_final.filter(updated_at__date__gte=data_inicio)
        if data_fim:
            qs_final = qs_final.filter(updated_at__date__lte=data_fim)

        por_mes_finalizacao = (
            qs_final
            .annotate(mes=TruncMonth('updated_at'))
            .values('mes')
            .annotate(quantidade=Count('id'))
            .order_by('mes')
        )

        # Biológico vs não-biológico
        por_biologico = [
            {'label': 'Biológico',     'quantidade': qs.filter(biologico=True).count()},
            {'label': 'Não Biológico', 'quantidade': qs.filter(biologico=False).count()},
        ]

        # Conformidade
        por_conformidade = [
            {'label': 'Conforme',     'quantidade': qs.filter(conformidade=True).count()},
            {'label': 'Não Conforme', 'quantidade': qs.filter(conformidade=False).count()},
        ]

        # Movimentações por mês (escopo de perfil/serviço + janela de data já em qs_mov)
        por_mes_mov = (
            qs_mov.filter(created_at__isnull=False)
            .annotate(mes=TruncMonth('created_at'))
            .values('mes')
            .annotate(quantidade=Count('id'))
            .order_by('mes')
        )

        # DNA por situação
        dna_por_situacao = (
            qs_dna.values('situacao')
            .annotate(quantidade=Count('id'))
            .order_by('-quantidade')
        )

        # DNA por finalidade de coleta
        dna_por_finalidade = (
            qs_dna.values('finalidade_coleta')
            .annotate(quantidade=Count('id'))
            .order_by('-quantidade')
        )

        # DNA por mês
        dna_por_mes = (
            qs_dna.filter(created_at__isnull=False)
            .annotate(mes=TruncMonth('created_at'))
            .values('mes')
            .annotate(quantidade=Count('id'))
            .order_by('mes')
        )

        # Matriz Serviço × Status (mesmo escopo/filtros dos cards de status)
        matriz_raw = (
            qs.values('servico_pericial__sigla', 'status')
            .annotate(quantidade=Count('id'))
            .order_by('servico_pericial__sigla', 'status')
        )
        matriz_servico_status = [
            {
                'servico':    i['servico_pericial__sigla'] or '?',
                'status':     i['status'],
                'quantidade': i['quantidade'],
            }
            for i in matriz_raw
        ]

        # -------------------------------------------------------------------
        # Alertas operacionais
        # -------------------------------------------------------------------
        limite_mov  = agora - timedelta(days=7)
        limite_vest = agora - timedelta(days=30)

        movs_pendentes = (
            qs_mov_base.filter(aceito=False, created_at__lte=limite_mov)
            .select_related('vestigio', 'servico_pericial', 'created_by')
            .order_by('created_at')[:20]
        )

        vest_parados = (
            qs_base.filter(
                status=Vestigio.Status.ANDAMENTO,
                updated_at__lte=limite_vest,
            )
            .select_related('servico_pericial', 'user_destino')
            .order_by('updated_at')[:20]
        )

        # -------------------------------------------------------------------
        # Resposta
        # -------------------------------------------------------------------
        def _fmt_mes(m):
            return {'mes': m['mes'].strftime('%Y-%m'), 'mes_nome': m['mes'].strftime('%b/%Y'), 'quantidade': m['quantidade']}

        return Response({
            'resumo': {
                'total_vestigios':   total_vestigios,
                'vestigios_ativos':  vestigios_ativos,
                'aguardando_aceite': aguardando_aceite,
                'finalizados_mes':   finalizados_mes,
                'total_dnas':        total_dnas,
                'biologicos_ativos': biologicos_ativos,
                'saiu_custodia':     saiu_custodia,
            },
            'cards_status': cards_status,
            'graficos': {
                'por_servico': [
                    {'sigla': i['servico_pericial__sigla'] or '?', 'nome': i['servico_pericial__nome'] or 'N/I', 'quantidade': i['quantidade']}
                    for i in por_servico
                ],
                'por_unidade': [
                    {'sigla': i['unidade_demandante__sigla'] or '?', 'nome': i['unidade_demandante__nome'] or 'N/I', 'quantidade': i['quantidade']}
                    for i in por_unidade
                ],
                'por_mes_cadastro':    [_fmt_mes(i) for i in por_mes_cadastro if i['mes']],
                'por_mes_finalizacao': [_fmt_mes(i) for i in por_mes_finalizacao if i['mes']],
                'por_mes_mov':         [_fmt_mes(i) for i in por_mes_mov if i['mes']],
                'por_biologico':       por_biologico,
                'por_conformidade':    por_conformidade,
                'dna_por_situacao': [
                    {'label': i['situacao'] or 'N/I', 'quantidade': i['quantidade']}
                    for i in dna_por_situacao
                ],
                'dna_por_finalidade': [
                    {'label': i['finalidade_coleta'] or 'N/I', 'quantidade': i['quantidade']}
                    for i in dna_por_finalidade
                ],
                'dna_por_mes':            [_fmt_mes(i) for i in dna_por_mes if i['mes']],
                'matriz_servico_status':  matriz_servico_status,
            },
            'alertas': {
                'movimentacoes_pendentes': [
                    {
                        'id':             m.pk,
                        'vestigio_id':    m.vestigio_id,
                        'vestigio_lacre': m.vestigio.lacre if m.vestigio else None,
                        'servico':        m.servico_pericial.sigla if m.servico_pericial else '?',
                        'registrado_por': m.created_by.nome_completo if m.created_by else '?',
                        'criado_em':      m.created_at.isoformat() if m.created_at else None,
                        'dias_pendente':  (agora - m.created_at).days if m.created_at else 0,
                    }
                    for m in movs_pendentes
                ],
                'vestigios_parados': [
                    {
                        'id':                 v.pk,
                        'lacre':              v.lacre,
                        'servico':            v.servico_pericial.sigla if v.servico_pericial else '?',
                        'responsavel':        v.user_destino.nome_completo if v.user_destino else 'N/A',
                        'ultima_atualizacao': v.updated_at.isoformat() if v.updated_at else None,
                        'dias_parado':        (agora - v.updated_at).days if v.updated_at else 0,
                    }
                    for v in vest_parados
                ],
            },
        })