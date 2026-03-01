from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, F, Case, When, Sum
from django.db.models.functions import Coalesce
from datetime import datetime

from .models import Ocorrencia, OcorrenciaExame
from .permissions import PodeVerRelatoriosGerenciais
from .pdf_generator import gerar_pdf_relatorios_gerenciais
from servicos_periciais.models import ServicoPericial
from cidades.models import Cidade
from usuarios.models import User
from classificacoes.models import ClassificacaoOcorrencia
from exames.models import Exame


def _montar_exames_hierarquicos(ids_ocorrencias):
    """
    Função auxiliar reutilizada pelo list() e gerar_pdf().
    Retorna a lista de exames agrupados por pai/filho.
    """
    por_exame_qs = (
        OcorrenciaExame.objects.filter(ocorrencia_id__in=ids_ocorrencias)
        .values(
            "exame__id",
            "exame__codigo",
            "exame__nome",
            "exame__parent__id",
            "exame__parent__codigo",
            "exame__parent__nome",
            "exame__servico_pericial__sigla",
        )
        .annotate(quantidade_total=Sum("quantidade"))
        .order_by("exame__servico_pericial__sigla", "exame__codigo")
    )

    pais_dict = {}
    for item in por_exame_qs:
        parent_id = item["exame__parent__id"]
        servico_sigla = item["exame__servico_pericial__sigla"] or "-"

        filho = {
            "codigo": item["exame__codigo"],
            "nome": item["exame__nome"],
            "quantidade": item["quantidade_total"],
        }

        if parent_id:
            if parent_id not in pais_dict:
                pais_dict[parent_id] = {
                    "codigo": item["exame__parent__codigo"],
                    "nome": item["exame__parent__nome"],
                    "servico_sigla": servico_sigla,
                    "quantidade_total": 0,
                    "filhos": [],
                }
            pais_dict[parent_id]["filhos"].append(filho)
            pais_dict[parent_id]["quantidade_total"] += item["quantidade_total"]
        else:
            exame_id = item["exame__id"]
            if exame_id not in pais_dict:
                pais_dict[exame_id] = {
                    "codigo": item["exame__codigo"],
                    "nome": item["exame__nome"],
                    "servico_sigla": servico_sigla,
                    "quantidade_total": item["quantidade_total"],
                    "filhos": [],
                }
            else:
                pais_dict[exame_id]["quantidade_total"] += item["quantidade_total"]

    return sorted(pais_dict.values(), key=lambda x: x["codigo"])


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

    def _aplicar_filtros(self, queryset, request):
        """Aplica filtros comuns ao queryset e retorna (queryset, filtros_info)"""
        data_inicio_str = request.query_params.get("data_inicio")
        data_fim_str = request.query_params.get("data_fim")
        servico_id = request.query_params.get("servico_id")
        cidade_id = request.query_params.get("cidade_id")
        perito_id = request.query_params.get("perito_id")
        classificacao_id = request.query_params.get("classificacao_id")

        filtros_info = {}

        if data_inicio_str:
            dt = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            queryset = queryset.filter(created_at__date__gte=dt)
            filtros_info["data_inicio"] = dt.strftime("%d/%m/%Y")

        if data_fim_str:
            dt = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
            queryset = queryset.filter(created_at__date__lte=dt)
            filtros_info["data_fim"] = dt.strftime("%d/%m/%Y")

        if servico_id:
            queryset = queryset.filter(servico_pericial_id=servico_id)
            try:
                filtros_info["servico_nome"] = ServicoPericial.objects.get(
                    pk=servico_id
                ).nome
            except ServicoPericial.DoesNotExist:
                pass

        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)
            try:
                filtros_info["cidade_nome"] = Cidade.objects.get(pk=cidade_id).nome
            except Cidade.DoesNotExist:
                pass

        if perito_id:
            queryset = queryset.filter(perito_atribuido_id=perito_id)
            try:
                filtros_info["perito_nome"] = User.objects.get(
                    pk=perito_id
                ).nome_completo
            except User.DoesNotExist:
                pass

        if classificacao_id:
            try:
                classificacao = ClassificacaoOcorrencia.objects.get(pk=classificacao_id)
                descendentes = classificacao.subgrupos.all().values_list(
                    "pk", flat=True
                )
                ids_para_filtrar = [classificacao.id] + list(descendentes)
                queryset = queryset.filter(classificacao_id__in=ids_para_filtrar)
                filtros_info["classificacao_nome"] = classificacao.nome
            except ClassificacaoOcorrencia.DoesNotExist:
                pass

        return queryset, filtros_info, perito_id

    def _gerar_dados(self, queryset, perito_id=None):
        """Gera todos os dados dos relatórios a partir do queryset filtrado"""

        # Grupo Principal
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

        # Classificação Específica
        por_classificacao_especifica = (
            queryset.filter(classificacao__parent__isnull=False)
            .values("classificacao__codigo", "classificacao__nome")
            .annotate(total=Count("id"))
            .order_by("classificacao__codigo")
        )

        # Produção por Perito
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

        # Produção por Serviço
        servicos_queryset = ServicoPericial.objects.filter(deleted_at__isnull=True)
        por_servico = (
            servicos_queryset.annotate(
                total_exames=Coalesce(
                    Sum(
                        "ocorrencias__ocorrenciaexame__quantidade",
                        filter=Q(ocorrencias__in=queryset),
                    ),
                    0,
                ),
                total=Coalesce(
                    Count(
                        "ocorrencias", filter=Q(ocorrencias__in=queryset), distinct=True
                    ),
                    0,
                ),
                finalizadas=Coalesce(
                    Count(
                        "ocorrencias",
                        filter=Q(
                            ocorrencias__in=queryset, ocorrencias__status="FINALIZADA"
                        ),
                        distinct=True,
                    ),
                    0,
                ),
                em_analise=Coalesce(
                    Count(
                        "ocorrencias",
                        filter=Q(
                            ocorrencias__in=queryset, ocorrencias__status="EM_ANALISE"
                        ),
                        distinct=True,
                    ),
                    0,
                ),
            )
            .values(
                "sigla", "nome", "total", "total_exames", "finalizadas", "em_analise"
            )
            .order_by("-total")
        )

        por_servico_formatado = [
            {
                "servico_pericial__sigla": item["sigla"],
                "servico_pericial__nome": item["nome"],
                "total": item["total"],
                "total_exames": item["total_exames"],
                "finalizadas": item["finalizadas"],
                "em_analise": item["em_analise"],
            }
            for item in por_servico
        ]

        # Exames com hierarquia pai/filho
        ids_ocorrencias = list(queryset.values_list("id", flat=True))
        por_exame_formatado = _montar_exames_hierarquicos(ids_ocorrencias)

        return {
            "por_grupo_principal": list(por_grupo_principal),
            "por_classificacao_especifica": list(por_classificacao_especifica),
            "producao_por_perito": list(por_perito),
            "por_servico": por_servico_formatado,
            "por_exame": por_exame_formatado,
        }

    def list(self, request):
        """Retorna os dados em JSON - URL: GET /api/relatorios-gerenciais/"""
        queryset = self.get_queryset()

        try:
            queryset, filtros_info, perito_id = self._aplicar_filtros(queryset, request)
        except (ValueError, TypeError):
            return Response(
                {"error": "Formato de filtro inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dados = self._gerar_dados(queryset, perito_id)
        return Response(dados)

    @action(detail=False, methods=["get"], url_path="pdf")
    def gerar_pdf(self, request):
        """Gera o PDF - URL: GET /api/relatorios-gerenciais/pdf/"""
        queryset = self.get_queryset()

        try:
            queryset, filtros_info, perito_id = self._aplicar_filtros(queryset, request)
        except (ValueError, TypeError):
            filtros_info = {}
            perito_id = None

        dados = self._gerar_dados(queryset, perito_id)
        return gerar_pdf_relatorios_gerenciais(dados, filtros_info, request)
