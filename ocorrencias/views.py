from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Count, F, Case, When, Sum  # <--- ADICIONADO SUM
from django.db.models.functions import Coalesce
from datetime import timedelta, datetime
from ocorrencias.endereco_models import EnderecoOcorrencia
from servicos_periciais.models import ServicoPericial
from usuarios.models import User
from classificacoes.models import ClassificacaoOcorrencia

from .models import Ocorrencia, OcorrenciaExame  # <--- ADICIONADO OcorrenciaExame
from .serializers import (
    EnderecoOcorrenciaSerializer,
    OcorrenciaCreateSerializer,
    OcorrenciaListSerializer,
    OcorrenciaDetailSerializer,
    OcorrenciaUpdateSerializer,
    OcorrenciaLixeiraSerializer,
    FinalizarComAssinaturaSerializer,
    ReabrirOcorrenciaSerializer,
)
from .permissions import (
    OcorrenciaPermission,
    PodeEditarOcorrencia,
    PodeFinalizarOcorrencia,
    PodeReabrirOcorrencia,
    PeritoAtribuidoRequired,
    PodeVerRelatoriosGerenciais,
)
from .filters import OcorrenciaFilter
from .pdf_generator import (
    gerar_pdf_ocorrencia,
    gerar_pdf_ocorrencias_por_perito,
    gerar_pdf_ocorrencias_por_ano,
    gerar_pdf_ocorrencias_por_status,
    gerar_pdf_ocorrencias_por_servico,
    gerar_pdf_ocorrencias_por_cidade,
    gerar_pdf_relatorio_geral,
)


class OcorrenciaViewSet(viewsets.ModelViewSet):
    queryset = (
        Ocorrencia.all_objects.select_related(
            "servico_pericial",
            "unidade_demandante",
            "autoridade__cargo",
            "cidade",
            "classificacao",
            "classificacao__parent",
            "procedimento_cadastrado__tipo_procedimento",
            "tipo_documento_origem",
            "perito_atribuido",
            "created_by",
            "updated_by",
            "finalizada_por",
            "reaberta_por",
        )
        .prefetch_related("exames_solicitados")
        .all()
    )
    permission_classes = [OcorrenciaPermission]
    filterset_class = OcorrenciaFilter
    search_fields = [
        "numero_ocorrencia",
        "perito_atribuido__nome_completo",
        "autoridade__nome",
    ]

    def get_permissions(self):
        if self.action == "relatorios_gerenciais":
            return [PodeVerRelatoriosGerenciais()]
        if self.action in ["adicionar_exames", "remover_exames", "definir_exames"]:
            return [PeritoAtribuidoRequired()]
        if self.action == "finalizar":
            return [PodeFinalizarOcorrencia()]
        if self.action == "reabrir":
            return [PodeReabrirOcorrencia()]
        if self.action in ["update", "partial_update"]:
            return [PodeEditarOcorrencia()]
        return [permission() for permission in self.permission_classes]

    def get_serializer_class(self):
        if self.action in ["list", "finalizadas", "pendentes"]:
            return OcorrenciaListSerializer
        if self.action == "lixeira":
            return OcorrenciaLixeiraSerializer
        if self.action == "finalizar":
            return FinalizarComAssinaturaSerializer
        if self.action == "reabrir":
            return ReabrirOcorrenciaSerializer
        if self.action in ["update", "partial_update"]:
            return OcorrenciaUpdateSerializer
        if self.action == "create":
            return OcorrenciaCreateSerializer
        return OcorrenciaDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if user.is_superuser or user.perfil == "ADMINISTRATIVO":
            if self.action not in ["lixeira", "restaurar"]:
                queryset = queryset.filter(deleted_at__isnull=True)
            return queryset

        return queryset.filter(
            servico_pericial__in=user.servicos_periciais.all(), deleted_at__isnull=True
        )

    @action(detail=False, methods=["get"], url_path="relatorios-gerenciais")
    def relatorios_gerenciais(self, request):
        queryset = self.get_queryset()

        data_inicio_str = request.query_params.get("data_inicio")
        data_fim_str = request.query_params.get("data_fim")
        servico_id = request.query_params.get("servico_id")
        cidade_id = request.query_params.get("cidade_id")
        perito_id = request.query_params.get("perito_id")
        classificacao_id = request.query_params.get("classificacao_id")

        try:
            if data_inicio_str:
                queryset = queryset.filter(
                    created_at__date__gte=datetime.strptime(
                        data_inicio_str, "%Y-%m-%d"
                    ).date()
                )
            if data_fim_str:
                queryset = queryset.filter(
                    created_at__date__lte=datetime.strptime(
                        data_fim_str, "%Y-%m-%d"
                    ).date()
                )
            if servico_id:
                queryset = queryset.filter(servico_pericial_id=servico_id)
            if cidade_id:
                queryset = queryset.filter(cidade_id=cidade_id)
            if perito_id:
                queryset = queryset.filter(perito_atribuido_id=perito_id)
            if classificacao_id:
                try:
                    classificacao = ClassificacaoOcorrencia.objects.get(
                        pk=classificacao_id
                    )
                    descendentes = classificacao.subgrupos.all().values_list(
                        "pk", flat=True
                    )
                    ids_para_filtrar = [classificacao.id] + list(descendentes)
                    queryset = queryset.filter(classificacao_id__in=ids_para_filtrar)
                except ClassificacaoOcorrencia.DoesNotExist:
                    pass
        except (ValueError, TypeError):
            return Response(
                {"error": "Formato de filtro inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        por_grupo_principal = (
            queryset.annotate(
                grupo_nome=Case(
                    When(
                        classificacao__parent__isnull=False,
                        then=F("classificacao__parent__nome"),
                    ),
                    default=F("classificacao__nome"),
                ),
                grupo_codigo=Case(
                    When(
                        classificacao__parent__isnull=False,
                        then=F("classificacao__parent__codigo"),
                    ),
                    default=F("classificacao__codigo"),
                ),
            )
            .values("grupo_nome", "grupo_codigo")
            .annotate(total=Count("id"))
            .order_by("grupo_codigo")
        )

        por_classificacao_especifica = (
            queryset.filter(classificacao__parent__isnull=False)
            .values("classificacao__codigo", "classificacao__nome")
            .annotate(total=Count("id"))
            .order_by("classificacao__codigo")
        )

        peritos_queryset = User.objects.filter(perfil="PERITO", status="ATIVO")
        if perito_id:
            peritos_queryset = peritos_queryset.filter(id=perito_id)
        por_perito = (
            peritos_queryset.annotate(
                total_ocorrencias=Coalesce(
                    Count(
                        "ocorrencias_atribuidas",
                        filter=Q(ocorrencias_atribuidas__in=queryset),
                    ),
                    0,
                ),
                finalizadas=Coalesce(
                    Count(
                        "ocorrencias_atribuidas",
                        filter=Q(
                            ocorrencias_atribuidas__in=queryset,
                            ocorrencias_atribuidas__status="FINALIZADA",
                        ),
                    ),
                    0,
                ),
                em_analise=Coalesce(
                    Count(
                        "ocorrencias_atribuidas",
                        filter=Q(
                            ocorrencias_atribuidas__in=queryset,
                            ocorrencias_atribuidas__status="EM_ANALISE",
                        ),
                    ),
                    0,
                ),
            )
            .values("nome_completo", "total_ocorrencias", "finalizadas", "em_analise")
            .order_by("-total_ocorrencias")
        )

        servicos_queryset = ServicoPericial.objects.filter(deleted_at__isnull=True)
        por_servico = (
            servicos_queryset.annotate(
                total=Coalesce(
                    Count("ocorrencias", filter=Q(ocorrencias__in=queryset)), 0
                ),
                finalizadas=Coalesce(
                    Count(
                        "ocorrencias",
                        filter=Q(
                            ocorrencias__in=queryset, ocorrencias__status="FINALIZADA"
                        ),
                    ),
                    0,
                ),
                em_analise=Coalesce(
                    Count(
                        "ocorrencias",
                        filter=Q(
                            ocorrencias__in=queryset, ocorrencias__status="EM_ANALISE"
                        ),
                    ),
                    0,
                ),
            )
            .values("sigla", "nome", "total", "finalizadas", "em_analise")
            .order_by("-total")
        )

        por_servico_formatado = [
            {
                "servico_pericial__sigla": item["sigla"],
                "servico_pericial__nome": item["nome"],
                "total": item["total"],
                "finalizadas": item["finalizadas"],
                "em_analise": item["em_analise"],
            }
            for item in por_servico
        ]

        return Response(
            {
                "por_grupo_principal": list(por_grupo_principal),
                "por_classificacao_especifica": list(por_classificacao_especifica),
                "producao_por_perito": list(por_perito),
                "por_servico": por_servico_formatado,
            }
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ocorrencia = serializer.save(created_by=request.user)

        response_serializer = OcorrenciaDetailSerializer(
            ocorrencia, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        ocorrencia = serializer.save(updated_by=request.user)

        response_serializer = OcorrenciaDetailSerializer(
            ocorrencia, context={"request": request}
        )
        return Response(response_serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def lixeira(self, request):
        queryset = self.get_queryset().filter(deleted_at__isnull=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def imprimir(self, request, pk=None):
        ocorrencia = self.get_object()
        pdf_response = gerar_pdf_ocorrencia(ocorrencia, request)
        return pdf_response

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"])
    def finalizar(self, request, pk=None):
        """Finaliza uma ocorrência com assinatura digital."""
        ocorrencia = self.get_object()

        if request.method == "POST":
            # Validação 1: Perito obrigatório
            if not ocorrencia.perito_atribuido:
                return Response(
                    {
                        "error": (
                            "❌ Não é possível finalizar esta ocorrência: Nenhum perito foi atribuído. "
                            "É obrigatório que um perito seja designado para a ocorrência antes da finalização. "
                            "Por favor, atribua um perito responsável e tente novamente."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validação 2: Status correto
            if ocorrencia.status != Ocorrencia.Status.EM_ANALISE:
                status_atual = ocorrencia.get_status_display()
                return Response(
                    {
                        "error": (
                            f'❌ Não é possível finalizar esta ocorrência: Status atual é "{status_atual}". '
                            'Apenas ocorrências com status "Em Análise" podem ser finalizadas. '
                            "Verifique o status da ocorrência e tente novamente."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validação 3: Ordens de Serviço pendentes
            from ordens_servico.models import OrdemServico

            ordens_pendentes = ocorrencia.ordens_servico.exclude(
                status=OrdemServico.Status.CONCLUIDA
            ).filter(deleted_at__isnull=True)

            if ordens_pendentes.exists():
                numeros_os = list(ordens_pendentes.values_list("numero_os", flat=True))
                return Response(
                    {
                        "error": (
                            f"❌ Não é possível finalizar a ocorrência: Existem Ordens de Serviço pendentes. "
                            f'As seguintes OS precisam ser concluídas ou canceladas primeiro: {", ".join(numeros_os)}. '
                            "Por favor, regularize essas ordens de serviço antes de finalizar a ocorrência."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validação 4: Já finalizada
            if ocorrencia.esta_finalizada:
                finalizada_por = (
                    ocorrencia.finalizada_por.nome_completo
                    if ocorrencia.finalizada_por
                    else "N/A"
                )
                data_finalizacao = (
                    ocorrencia.data_finalizacao.strftime("%d/%m/%Y às %H:%M")
                    if ocorrencia.data_finalizacao
                    else "N/A"
                )
                return Response(
                    {
                        "error": (
                            "❌ Esta ocorrência já foi finalizada anteriormente. "
                            f"Finalizada por: {finalizada_por} em {data_finalizacao}. "
                            "Não é possível finalizar uma ocorrência que já está finalizada."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validação 5: Senha (via serializer)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Finalização com assinatura
            ip_address = request.META.get("REMOTE_ADDR", "127.0.0.1")
            ocorrencia.finalizar_com_assinatura(request.user, ip_address)

            response_serializer = OcorrenciaDetailSerializer(
                ocorrencia, context={"request": request}
            )
            return Response(
                {
                    "message": (
                        f"✅ Ocorrência {ocorrencia.numero_ocorrencia} finalizada com sucesso! "
                        f"Finalizada por: {request.user.nome_completo}."
                    ),
                    "ocorrencia": response_serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        # GET method - retorna formulário/info
        serializer = self.get_serializer(instance=ocorrencia)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"])
    def reabrir(self, request, pk=None):
        ocorrencia = self.get_object()
        if request.method == "POST":
            if not ocorrencia.esta_finalizada:
                return Response(
                    {"error": "Esta ocorrência não está finalizada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                ip_address = request.META.get("REMOTE_ADDR", "127.0.0.1")
                motivo = serializer.validated_data.get("motivo_reabertura")
                ocorrencia.reabrir(request.user, motivo, ip_address)
                response_serializer = OcorrenciaDetailSerializer(
                    ocorrencia, context={"request": request}
                )
                return Response(
                    {
                        "message": "Ocorrência reaberta com sucesso.",
                        "ocorrencia": response_serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance=ocorrencia)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"])
    def atribuir_perito(self, request, pk=None):
        ocorrencia = self.get_object()
        if ocorrencia.esta_finalizada:
            return Response(
                {
                    "error": "Não é possível atribuir perito a uma ocorrência finalizada."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        perito_id = request.data.get("perito_id")
        if not perito_id:
            return Response(
                {"error": "perito_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from usuarios.models import User

            perito = User.objects.get(id=perito_id, perfil="PERITO")
            if ocorrencia.perito_atribuido and not request.user.is_superuser:
                return Response(
                    {
                        "error": "Apenas super administradores podem alterar o perito já atribuído."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            ocorrencia.perito_atribuido = perito
            ocorrencia.updated_by = request.user
            ocorrencia.save()
            serializer = self.get_serializer(ocorrencia)
            return Response(
                {
                    "message": f"Perito {perito.nome_completo} atribuído com sucesso.",
                    "ocorrencia": serializer.data,
                }
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Perito não encontrado."}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"])
    def finalizadas(self, request):
        queryset = (
            self.get_queryset()
            .filter(status="FINALIZADA", finalizada_por__isnull=False)
            .order_by("-data_assinatura_finalizacao")
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": queryset.count(), "results": serializer.data})

    @action(detail=False, methods=["get"])
    def pendentes(self, request):
        queryset = (
            self.get_queryset().exclude(status="FINALIZADA").order_by("-created_at")
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": queryset.count(), "results": serializer.data})

    @action(detail=True, methods=["get"])
    def historico_assinatura(self, request, pk=None):
        ocorrencia = self.get_object()
        if not ocorrencia.esta_finalizada:
            return Response(
                {"error": "Esta ocorrência não foi finalizada ainda."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "numero_ocorrencia": ocorrencia.numero_ocorrencia,
                "assinatura_digital": {
                    "finalizada_por": {
                        "id": ocorrencia.finalizada_por.id,
                        "nome": ocorrencia.finalizada_por.nome_completo,
                        "perfil": ocorrencia.finalizada_por.perfil,
                    },
                    "data_assinatura": ocorrencia.data_assinatura_finalizacao,
                    "ip_origem": ocorrencia.ip_assinatura_finalizacao,
                },
            }
        )

    @action(detail=True, methods=["post"])
    def adicionar_exames(self, request, pk=None):
        ocorrencia = self.get_object()

        if ocorrencia.esta_finalizada:
            return Response(
                {
                    "error": "Não é possível alterar exames de uma ocorrência finalizada."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if ocorrencia.perito_atribuido:
            if not user.is_superuser and user.id != ocorrencia.perito_atribuido.id:
                return Response(
                    {
                        "error": "Apenas o perito atribuído pode alterar os exames desta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        exames_ids = request.data.get("exames_ids", [])
        if not isinstance(exames_ids, list):
            return Response(
                {"error": "O campo 'exames_ids' deve ser uma lista de IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if exames_ids:
            from exames.models import Exame

            existing_ids = list(
                Exame.objects.filter(id__in=exames_ids).values_list("id", flat=True)
            )
            invalid_ids = set(exames_ids) - set(existing_ids)
            if invalid_ids:
                return Response(
                    {"error": f"Exames inválidos: {list(invalid_ids)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ADAPTADO PARA TABELA INTERMEDIÁRIA
        for eid in exames_ids:
            OcorrenciaExame.objects.get_or_create(
                ocorrencia=ocorrencia, exame_id=eid, defaults={"quantidade": 1}
            )

        serializer = OcorrenciaDetailSerializer(
            ocorrencia, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def remover_exames(self, request, pk=None):
        ocorrencia = self.get_object()

        if ocorrencia.esta_finalizada:
            return Response(
                {
                    "error": "Não é possível alterar exames de uma ocorrência finalizada."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if ocorrencia.perito_atribuido:
            if not user.is_superuser and user.id != ocorrencia.perito_atribuido.id:
                return Response(
                    {
                        "error": "Apenas o perito atribuído pode alterar os exames desta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        exames_ids = request.data.get("exames_ids", [])
        if not isinstance(exames_ids, list):
            return Response(
                {"error": "O campo 'exames_ids' deve ser uma lista de IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ADAPTADO PARA TABELA INTERMEDIÁRIA
        if exames_ids:
            OcorrenciaExame.objects.filter(
                ocorrencia=ocorrencia, exame_id__in=exames_ids
            ).delete()

        serializer = OcorrenciaDetailSerializer(
            ocorrencia, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def definir_exames(self, request, pk=None):
        """
        Define exames com suporte a quantidade.
        """
        ocorrencia = self.get_object()

        if ocorrencia.esta_finalizada:
            return Response(
                {
                    "error": "Não é possível alterar exames de uma ocorrência finalizada."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if ocorrencia.perito_atribuido:
            if not user.is_superuser and user.id != ocorrencia.perito_atribuido.id:
                return Response(
                    {"error": "Apenas o perito atribuído pode alterar os exames."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Suporta ambos os formatos (apenas IDs ou lista de objetos com qtd)
        exames_data = request.data.get("exames")
        exames_ids = request.data.get("exames_ids")

        OcorrenciaExame.objects.filter(ocorrencia=ocorrencia).delete()
        novos_objetos = []

        if exames_data and isinstance(exames_data, list):
            for item in exames_data:
                if isinstance(item, dict):
                    exame_id = item.get("id")
                    qtd = int(item.get("quantidade", 1))
                else:
                    exame_id = item
                    qtd = 1

                if exame_id:
                    novos_objetos.append(
                        OcorrenciaExame(
                            ocorrencia=ocorrencia, exame_id=exame_id, quantidade=qtd
                        )
                    )

        elif exames_ids and isinstance(exames_ids, list):
            for exame_id in exames_ids:
                novos_objetos.append(
                    OcorrenciaExame(
                        ocorrencia=ocorrencia, exame_id=exame_id, quantidade=1
                    )
                )

        if novos_objetos:
            OcorrenciaExame.objects.bulk_create(novos_objetos)

        serializer = OcorrenciaDetailSerializer(
            ocorrencia, context={"request": request}
        )
        return Response(
            {
                "message": f"{len(novos_objetos)} exames definidos com sucesso.",
                "ocorrencia": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def exames_disponiveis(self, request):
        from exames.models import Exame

        search = request.GET.get("search", "")
        servico_pericial_id = request.GET.get("servico_pericial_id", "")
        page_size = int(request.GET.get("page_size", 20))
        page = int(request.GET.get("page", 1))

        queryset = Exame.objects.all().order_by("codigo")

        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) | Q(codigo__icontains=search)
            )

        if servico_pericial_id:
            queryset = queryset.filter(servico_pericial_id=servico_pericial_id)

        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        exames = queryset[start:end]

        from exames.serializers import ExameNestedSerializer

        serializer = ExameNestedSerializer(exames, many=True)

        return Response(
            {
                "exames": serializer.data,
                "pagination": {
                    "count": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size,
                    "has_next": end < total,
                    "has_previous": page > 1,
                },
            }
        )

    @action(detail=True, methods=["get"])
    def exames_atuais(self, request, pk=None):
        ocorrencia = self.get_object()

        # Usar o novo serializer se disponível (importando dentro para evitar ciclo)
        from .serializers import OcorrenciaExameSerializer

        # Busca da tabela intermediária
        qs = OcorrenciaExame.objects.filter(ocorrencia=ocorrencia).select_related(
            "exame"
        )
        serializer = OcorrenciaExameSerializer(qs, many=True)

        return Response(
            {
                "ocorrencia_id": ocorrencia.id,
                "numero_ocorrencia": ocorrencia.numero_ocorrencia,
                "exames_atuais": serializer.data,
                "total_exames": qs.count(),
            }
        )

    @action(
        detail=False, methods=["get"], url_path="relatorio-perito/(?P<perito_id>[^/.]+)"
    )
    def relatorio_por_perito(self, request, perito_id=None, *args, **kwargs):
        try:
            perito_id = int(perito_id)
        except ValueError:
            return Response(
                {"error": "ID do perito deve ser um número válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return gerar_pdf_ocorrencias_por_perito(perito_id, request)

    @action(detail=False, methods=["get"], url_path="relatorio-ano/(?P<ano>[^/.]+)")
    def relatorio_por_ano(self, request, ano=None, *args, **kwargs):
        try:
            ano = int(ano)
            if ano < 2000 or ano > 2050:
                raise ValueError("Ano inválido")
        except ValueError:
            return Response(
                {"error": "Ano deve ser um número válido entre 2000 e 2050."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return gerar_pdf_ocorrencias_por_ano(ano, request)

    @action(
        detail=False,
        methods=["get"],
        url_path="relatorio-status/(?P<status_param>[^/.]+)",
    )
    def relatorio_por_status(self, request, status_param=None, *args, **kwargs):
        status_validos = [choice[0] for choice in Ocorrencia.Status.choices]
        if status_param not in status_validos:
            return Response(
                {"error": f"Status inválido. Opções: {', '.join(status_validos)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return gerar_pdf_ocorrencias_por_status(status_param, request)

    @action(
        detail=False,
        methods=["get"],
        url_path="relatorio-servico/(?P<servico_id>[^/.]+)",
    )
    def relatorio_por_servico(self, request, servico_id=None, *args, **kwargs):
        try:
            servico_id = int(servico_id)
        except ValueError:
            return Response(
                {"error": "ID do serviço deve ser um número válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return gerar_pdf_ocorrencias_por_servico(servico_id, request)

    @action(
        detail=False, methods=["get"], url_path="relatorio-cidade/(?P<cidade_id>[^/.]+)"
    )
    def relatorio_por_cidade(self, request, cidade_id=None, *args, **kwargs):
        try:
            cidade_id = int(cidade_id)
        except ValueError:
            return Response(
                {"error": "ID da cidade deve ser um número válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return gerar_pdf_ocorrencias_por_cidade(cidade_id, request)

    @action(detail=False, methods=["get"], url_path="relatorio-geral")
    def relatorio_geral(self, request, *args, **kwargs):
        return gerar_pdf_relatorio_geral(request)

    @action(detail=False, methods=["get"])
    def estatisticas(self, request):
        user = self.request.user
        hoje = timezone.now().date()
        inicio_mes = hoje.replace(day=1)
        servico_id = request.GET.get("servico_id", None)

        if servico_id in ["null", "", "undefined"]:
            servico_id = None

        if user.perfil == "PERITO":
            minhas = Ocorrencia.objects.filter(
                perito_atribuido=user, deleted_at__isnull=True
            )

            if servico_id:
                minhas = minhas.filter(servico_pericial_id=servico_id)
                servicos_ids = [int(servico_id)]
            else:
                servicos_ids = list(
                    user.servicos_periciais.values_list("id", flat=True)
                )

            do_servico = Ocorrencia.objects.filter(
                servico_pericial_id__in=servicos_ids, deleted_at__isnull=True
            )

            data_limite = hoje - timedelta(days=20)
            atrasadas = minhas.filter(
                status__in=["AGUARDANDO_PERITO", "EM_ANALISE"],
                created_at__date__lt=data_limite,
            )

            finalizadas_mes = minhas.filter(
                status="FINALIZADA", data_finalizacao__gte=inicio_mes
            )

            ultimas = minhas.order_by("-created_at")[:5].values(
                "id", "numero_ocorrencia", "status", "created_at"
            )

            total_minhas = minhas.count()
            total_finalizadas = minhas.filter(status="FINALIZADA").count()
            taxa_finalizacao = (
                (total_finalizadas / total_minhas * 100) if total_minhas > 0 else 0
            )

            total_servico = do_servico.count()
            participacao = (
                (total_minhas / total_servico * 100) if total_servico > 0 else 0
            )

            # ✅ AQUI: Soma de quantidades (total_exames)
            por_servico_qs = (
                ServicoPericial.objects.filter(
                    id__in=servicos_ids, deleted_at__isnull=True
                )
                .annotate(
                    total=Count(
                        "ocorrencias",
                        filter=Q(
                            ocorrencias__in=minhas, ocorrencias__deleted_at__isnull=True
                        ),
                    ),
                    total_exames=Coalesce(
                        Sum(
                            "exames__ocorrenciaexame__quantidade",
                            filter=Q(exames__ocorrenciaexame__ocorrencia__in=minhas),
                        ),
                        0,
                    ),
                )
                .values("sigla", "nome", "total", "total_exames")
                .order_by("-total")
            )

            por_servico = [
                {
                    "servico_pericial__sigla": item["sigla"],
                    "servico_pericial__nome": item["nome"],
                    "total": item["total"],
                    "total_exames": item["total_exames"],  # Envia para o front
                }
                for item in por_servico_qs
            ]

            return Response(
                {
                    "minhas_ocorrencias": {
                        "total": total_minhas,
                        "aguardando": minhas.filter(status="AGUARDANDO_PERITO").count(),
                        "em_analise": minhas.filter(status="EM_ANALISE").count(),
                        "finalizadas": total_finalizadas,
                        "atrasadas": atrasadas.count(),
                        "finalizadas_este_mes": finalizadas_mes.count(),
                        "taxa_finalizacao": round(taxa_finalizacao, 1),
                    },
                    "servico": {
                        "total_geral": total_servico,
                        "minha_participacao": round(participacao, 1),
                    },
                    "ultimas_ocorrencias": list(ultimas),
                    "por_servico": por_servico,
                }
            )

        elif user.perfil == "OPERACIONAL":
            servicos_ids = list(user.servicos_periciais.values_list("id", flat=True))

            if servico_id:
                servicos_ids = (
                    [int(servico_id)]
                    if int(servico_id) in servicos_ids
                    else servicos_ids
                )

            todas = Ocorrencia.objects.filter(
                servico_pericial_id__in=servicos_ids, deleted_at__isnull=True
            )

            data_limite = hoje - timedelta(days=20)
            atrasadas = todas.filter(
                status__in=["AGUARDANDO_PERITO", "EM_ANALISE"],
                created_at__date__lt=data_limite,
            )

            finalizadas_mes = todas.filter(
                status="FINALIZADA", data_finalizacao__gte=inicio_mes
            )

            por_servico_qs = (
                ServicoPericial.objects.filter(
                    id__in=servicos_ids, deleted_at__isnull=True
                )
                .annotate(
                    total=Count(
                        "ocorrencias",
                        filter=Q(
                            ocorrencias__in=todas, ocorrencias__deleted_at__isnull=True
                        ),
                    ),
                    total_exames=Coalesce(
                        Sum(
                            "exames__ocorrenciaexame__quantidade",
                            filter=Q(exames__ocorrenciaexame__ocorrencia__in=todas),
                        ),
                        0,
                    ),
                )
                .values("sigla", "nome", "total", "total_exames")
                .order_by("-total")
            )

            por_servico = [
                {
                    "servico_pericial__sigla": item["sigla"],
                    "servico_pericial__nome": item["nome"],
                    "total": item["total"],
                    "total_exames": item["total_exames"],
                }
                for item in por_servico_qs
            ]

            dias_30 = hoje - timedelta(days=30)
            criadas_30dias = todas.filter(created_at__date__gte=dias_30).count()
            finalizadas_30dias = todas.filter(
                status="FINALIZADA", data_finalizacao__gte=dias_30
            ).count()

            return Response(
                {
                    "geral": {
                        "total": todas.count(),
                        "aguardando": todas.filter(status="AGUARDANDO_PERITO").count(),
                        "em_analise": todas.filter(status="EM_ANALISE").count(),
                        "finalizadas": todas.filter(status="FINALIZADA").count(),
                        "sem_perito": todas.filter(
                            perito_atribuido__isnull=True
                        ).count(),
                        "atrasadas": atrasadas.count(),
                        "finalizadas_este_mes": finalizadas_mes.count(),
                    },
                    "ultimos_30_dias": {
                        "criadas": criadas_30dias,
                        "finalizadas": finalizadas_30dias,
                    },
                    "por_servico": por_servico,
                }
            )

        elif user.perfil == "ADMINISTRATIVO" or user.is_superuser:
            todas = Ocorrencia.objects.filter(deleted_at__isnull=True)

            if servico_id:
                todas = todas.filter(servico_pericial_id=servico_id)

            data_limite = hoje - timedelta(days=20)
            atrasadas = todas.filter(
                status__in=["AGUARDANDO_PERITO", "EM_ANALISE"],
                created_at__date__lt=data_limite,
            )

            finalizadas_mes = todas.filter(
                status="FINALIZADA", data_finalizacao__gte=inicio_mes
            )

            if servico_id:
                servicos_ids = [int(servico_id)]
            else:
                servicos_ids = list(
                    ServicoPericial.objects.filter(deleted_at__isnull=True).values_list(
                        "id", flat=True
                    )
                )

            por_servico_qs = (
                ServicoPericial.objects.filter(
                    id__in=servicos_ids, deleted_at__isnull=True
                )
                .annotate(
                    total=Count(
                        "ocorrencias",
                        filter=Q(
                            ocorrencias__in=todas, ocorrencias__deleted_at__isnull=True
                        ),
                    ),
                    total_exames=Coalesce(
                        Sum(
                            "exames__ocorrenciaexame__quantidade",
                            filter=Q(exames__ocorrenciaexame__ocorrencia__in=todas),
                        ),
                        0,
                    ),
                )
                .values("sigla", "nome", "total", "total_exames")
                .order_by("-total")
            )

            por_servico = [
                {
                    "servico_pericial__sigla": item["sigla"],
                    "servico_pericial__nome": item["nome"],
                    "total": item["total"],
                    "total_exames": item["total_exames"],
                }
                for item in por_servico_qs
            ]

            dias_30 = hoje - timedelta(days=30)
            criadas_30dias = todas.filter(created_at__date__gte=dias_30).count()
            finalizadas_30dias = todas.filter(
                status="FINALIZADA", data_finalizacao__gte=dias_30
            ).count()

            return Response(
                {
                    "geral": {
                        "total": todas.count(),
                        "aguardando": todas.filter(status="AGUARDANDO_PERITO").count(),
                        "em_analise": todas.filter(status="EM_ANALISE").count(),
                        "finalizadas": todas.filter(status="FINALIZADA").count(),
                        "sem_perito": todas.filter(
                            perito_atribuido__isnull=True
                        ).count(),
                        "atrasadas": atrasadas.count(),
                        "finalizadas_este_mes": finalizadas_mes.count(),
                    },
                    "ultimos_30_dias": {
                        "criadas": criadas_30dias,
                        "finalizadas": finalizadas_30dias,
                    },
                    "por_servico": por_servico,
                }
            )

        return Response({"detail": "Perfil não reconhecido"}, status=400)

    @action(detail=True, methods=["post"])
    def vincular_procedimento(self, request, pk=None):
        """
        Vincula ou desvincula um procedimento a uma ocorrência,
        registrando a alteração para fins de auditoria.
        """
        ocorrencia = self.get_object()
        user = request.user

        if ocorrencia.esta_finalizada:
            return Response(
                {
                    "error": "Não é possível alterar o vínculo de uma ocorrência finalizada."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ocorrencia.perito_atribuido:
            is_perito_da_ocorrencia = user.id == ocorrencia.perito_atribuido.id
            if not user.is_superuser and not is_perito_da_ocorrencia:
                return Response(
                    {
                        "error": "Você não tem permissão para fazer isso. Apenas o perito da ocorrência ou um super administrador pode alterar o vínculo."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        procedimento_id = request.data.get("procedimento_cadastrado_id")

        try:
            from procedimentos_cadastrados.models import ProcedimentoCadastrado
            from .models import HistoricoVinculacao

            procedimento_antigo = ocorrencia.procedimento_cadastrado
            procedimento_novo = None
            message = ""

            if procedimento_id is None:
                if not procedimento_antigo:
                    return Response(
                        {
                            "message": "A ocorrência já não possuía procedimento vinculado."
                        },
                        status=status.HTTP_200_OK,
                    )

                # ✅ CORRIGIDO: Usando __str__() do modelo
                message = (
                    f"Procedimento {procedimento_antigo} desvinculado com sucesso."
                )
                ocorrencia.procedimento_cadastrado = None
            else:
                procedimento_novo = ProcedimentoCadastrado.objects.get(
                    id=procedimento_id
                )
                ocorrencia.procedimento_cadastrado = procedimento_novo
                # ✅ CORRIGIDO: Usando __str__() do modelo
                message = f"Procedimento {procedimento_novo} vinculado com sucesso."

            ocorrencia.updated_by = request.user
            ocorrencia.save(
                update_fields=["procedimento_cadastrado", "updated_by", "updated_at"]
            )

            HistoricoVinculacao.objects.create(
                ocorrencia=ocorrencia,
                procedimento_antigo=procedimento_antigo,
                procedimento_novo=procedimento_novo,
                usuario=request.user,
            )

            serializer = self.get_serializer(ocorrencia)
            return Response({"message": message, "ocorrencia": serializer.data})

        except ProcedimentoCadastrado.DoesNotExist:
            return Response(
                {"error": "Procedimento com o ID fornecido não foi encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Erro inesperado em vincular_procedimento: {str(e)}")
            return Response(
                {"error": f"Ocorreu um erro inesperado no servidor: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # =================================================================
    #  NOVO MÓDULO: CALENDÁRIO (Visualização por Data do Fato)
    # =================================================================
    @action(detail=False, methods=["get"], url_path="dados-calendario")
    def dados_calendario(self, request):
        """
        Endpoint exclusivo para o FullCalendar.
        Retorna ocorrências filtradas pelo range de datas visível no calendário.
        """
        # O FullCalendar envia automaticamente 'start' e 'end' (ex: 2025-01-01)
        start_date = request.query_params.get("start")
        end_date = request.query_params.get("end")

        # 1. Segurança: Usa o seu get_queryset() existente.
        # Assim, se o usuário for PERITO, só vê as dele. Se for ADM, vê tudo.
        queryset = self.filter_queryset(self.get_queryset())

        # 2. Filtro de Data (Crucial para performance com milhares de registros)
        if start_date and end_date:
            # Remove horário da string se vier (ex: 2025-01-01T00:00:00 -> 2025-01-01)
            start = start_date.split("T")[0]
            end = end_date.split("T")[0]

            queryset = queryset.filter(
                created_at__range=[start, end], created_at__isnull=False
            )

        # 3. Busca Otimizada (.values): Pega só o necessário para pintar o calendário
        # Isso é muito mais rápido que o Serializer padrão
        dados = queryset.values(
            "id",
            "numero_ocorrencia",
            "created_at",
            "hora_fato",
            "status",
            "classificacao__nome",  # Para mostrar no título
        )

        eventos = []

        # Cores baseadas no seu Status Choices
        cores = {
            "AGUARDANDO_PERITO": "#ffc107",  # Amarelo
            "EM_ANALISE": "#0d6efd",  # Azul
            "FINALIZADA": "#198754",  # Verde
        }

        from datetime import datetime

        for item in dados:
            d_cadastro = item["created_at"]
            data_completa = datetime.fromisoformat(str(d_cadastro))
            h_cadastro = data_completa.time().replace(second=0, microsecond=0)

            # Cria string ISO (ex: "2025-11-21T14:30:00")
            dt_iso = datetime.combine(d_cadastro, h_cadastro).isoformat()
            # print (str(dt_iso)) # Comentado para limpar logs
            titulo = f"{item['numero_ocorrencia']}"
            if item.get("classificacao__nome"):
                titulo += f" - {item['classificacao__nome']}"

            eventos.append(
                {
                    "id": item["id"],
                    "title": titulo,
                    "start": dt_iso,
                    "color": cores.get(
                        item["status"], "#6c757d"
                    ),  # Cinza se status for estranho
                    "allDay": h_cadastro is None,  # Se não tem hora, é dia todo
                    "extendedProps": {"status": item["status"]},
                }
            )

        return Response(eventos)


class EnderecoOcorrenciaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar endereços de ocorrências.
    Permite criar, atualizar e consultar endereços.
    """

    queryset = EnderecoOcorrencia.objects.filter(deleted_at__isnull=True)
    serializer_class = EnderecoOcorrenciaSerializer
    permission_classes = [OcorrenciaPermission]

    def get_queryset(self):
        """Filtra endereços baseado nas permissões do usuário"""
        user = self.request.user
        queryset = self.queryset

        if user.is_superuser or user.perfil == "ADMINISTRATIVO":
            return queryset

        return queryset.filter(ocorrencia__perito_atribuido=user)

    # ========================================
    # ✅ ADICIONE ESTE MÉTODO AQUI
    # ========================================

    @action(detail=True, methods=["post"], url_path="geocodificar")
    def geocodificar_endereco(self, request, pk=None):
        """
        Geocodifica um endereço específico manualmente.
        POST /api/enderecos/{id}/geocodificar/
        """
        endereco = self.get_object()

        # Validações
        if endereco.tipo != "EXTERNA":
            return Response(
                {"error": "Apenas endereços externos podem ser geocodificados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if endereco.coordenadas_manuais:
            return Response(
                {
                    "error": "Este endereço possui coordenadas manuais que não devem ser sobrescritas."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not endereco.logradouro:
            return Response(
                {"error": "Endereço não possui logradouro para geocodificação."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Geocodifica
        sucesso = endereco.geocodificar_async()

        if sucesso:
            serializer = self.get_serializer(endereco)
            return Response(
                {
                    "message": "Endereço geocodificado com sucesso.",
                    "endereco": serializer.data,
                }
            )
        else:
            return Response(
                {"error": "Não foi possível geocodificar o endereço. Tente novamente."},
                status=status.HTTP_400_BAD_REQUEST,
            )
