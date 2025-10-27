from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, F, Case, When
from django.db.models.functions import Coalesce
from datetime import datetime

from .models import Ocorrencia
from .permissions import PodeVerRelatoriosGerenciais
from .pdf_generator import gerar_pdf_relatorios_gerenciais
from servicos_periciais.models import ServicoPericial
from cidades.models import Cidade
from usuarios.models import User
from classificacoes.models import ClassificacaoOcorrencia


class RelatoriosGerenciaisViewSet(viewsets.ViewSet):
    """ViewSet dedicado aos relatórios gerenciais"""

    permission_classes = [PodeVerRelatoriosGerenciais]

    def get_queryset(self):
        """Pega as ocorrências com base nas permissões do usuário"""
        user = self.request.user
        queryset = Ocorrencia.objects.filter(deleted_at__isnull=True)

        if not (user.is_superuser or user.perfil == "ADMINISTRATIVO"):
            queryset = queryset.filter(
                servico_pericial__in=user.servicos_periciais.all()
            )

        return queryset

    def list(self, request):
        """Retorna os dados em JSON - URL: GET /api/relatorios-gerenciais/"""
        queryset = self.get_queryset()

        # Pega os filtros da URL
        data_inicio_str = request.query_params.get("data_inicio")
        data_fim_str = request.query_params.get("data_fim")
        servico_id = request.query_params.get("servico_id")
        cidade_id = request.query_params.get("cidade_id")
        perito_id = request.query_params.get("perito_id")
        classificacao_id = request.query_params.get("classificacao_id")

        # Aplica os filtros
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

        # Gera os dados
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

    @action(detail=False, methods=["get"], url_path="pdf")
    def gerar_pdf(self, request):
        """Gera o PDF - URL: GET /api/relatorios-gerenciais/pdf/"""
        queryset = self.get_queryset()

        # Pega os filtros
        data_inicio_str = request.query_params.get("data_inicio")
        data_fim_str = request.query_params.get("data_fim")
        servico_id = request.query_params.get("servico_id")
        cidade_id = request.query_params.get("cidade_id")
        perito_id = request.query_params.get("perito_id")
        classificacao_id = request.query_params.get("classificacao_id")

        filtros_info = {}

        # Aplica os filtros
        try:
            if data_inicio_str:
                data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__date__gte=data_inicio)
                filtros_info["data_inicio"] = data_inicio.strftime("%d/%m/%Y")

            if data_fim_str:
                data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__date__lte=data_fim)
                filtros_info["data_fim"] = data_fim.strftime("%d/%m/%Y")

            if servico_id:
                queryset = queryset.filter(servico_pericial_id=servico_id)
                try:
                    servico = ServicoPericial.objects.get(pk=servico_id)
                    filtros_info["servico_nome"] = f"{servico.sigla} - {servico.nome}"
                except ServicoPericial.DoesNotExist:
                    pass

            if cidade_id:
                queryset = queryset.filter(cidade_id=cidade_id)
                try:
                    cidade = Cidade.objects.get(pk=cidade_id)
                    filtros_info["cidade_nome"] = cidade.nome
                except Cidade.DoesNotExist:
                    pass

            if perito_id:
                queryset = queryset.filter(perito_atribuido_id=perito_id)
                try:
                    perito = User.objects.get(pk=perito_id)
                    filtros_info["perito_nome"] = perito.nome_completo
                except User.DoesNotExist:
                    pass

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
                    filtros_info["classificacao_nome"] = classificacao.nome
                except ClassificacaoOcorrencia.DoesNotExist:
                    pass

        except (ValueError, TypeError):
            return Response(
                {"error": "Formato de filtro inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Gera os dados
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

        # Prepara os dados
        dados = {
            "por_grupo_principal": list(por_grupo_principal),
            "por_classificacao_especifica": list(por_classificacao_especifica),
            "producao_por_perito": list(por_perito),
            "por_servico": por_servico_formatado,
        }

        # Chama a função que gera o PDF
        return gerar_pdf_relatorios_gerenciais(dados, filtros_info, request)
