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
    Função definitiva para agrupar exames em árvore (Pai/Filho).
    À prova de duplicatas e infalível na soma.
    """
    itens_agrupados = (
        OcorrenciaExame.objects.filter(ocorrencia_id__in=ids_ocorrencias)
        .values("exame_id")
        .annotate(qtd=Sum("quantidade"))
    )

    if not itens_agrupados:
        return []

    qtd_map = {item["exame_id"]: item["qtd"] for item in itens_agrupados}
    exames_com_laudo_ids = list(qtd_map.keys())

    # Busca os exames que tiveram laudos + os pais deles
    exames_db = Exame.objects.select_related("parent", "servico_pericial").filter(
        id__in=exames_com_laudo_ids
    )

    pais_ids_necessarios = set()
    for ex in exames_db:
        if ex.parent_id:
            pais_ids_necessarios.add(ex.parent_id)

    pais_faltantes = (
        Exame.objects.select_related("servico_pericial")
        .filter(id__in=pais_ids_necessarios)
        .exclude(id__in=exames_com_laudo_ids)
    )

    todos_exames_map = {ex.id: ex for ex in list(exames_db) + list(pais_faltantes)}

    arvore = {}

    # Primeiro laço: Garante que TODOS os PAIS existam na árvore
    for ex_id, ex in todos_exames_map.items():
        if ex.parent_id is None:  # É um pai ou raiz
            if ex.id not in arvore:
                arvore[ex.id] = {
                    "codigo": ex.codigo,
                    "nome": ex.nome,
                    "servico_sigla": (
                        ex.servico_pericial.sigla if ex.servico_pericial else "-"
                    ),
                    "quantidade_total": 0,
                    "filhos": [],
                }

    # Segundo laço: Distribui as quantidades e os filhos
    for exame_id, qtd in qtd_map.items():
        exame = todos_exames_map.get(exame_id)
        if not exame:
            continue

        if exame.parent_id:  # É filho
            pai = todos_exames_map.get(exame.parent_id)
            if pai and pai.id in arvore:
                arvore[pai.id]["filhos"].append(
                    {"codigo": exame.codigo, "nome": exame.nome, "quantidade": qtd}
                )
                arvore[pai.id]["quantidade_total"] += qtd
        else:  # É pai que recebeu laudo direto
            if exame.id in arvore:
                arvore[exame.id]["quantidade_total"] += qtd

    def sort_key(codigo):
        return [int(p) if p.isdigit() else p for p in (codigo or "").split(".")]

    for pai in arvore.values():
        pai["filhos"] = sorted(pai["filhos"], key=lambda x: sort_key(x["codigo"]))

    resultado = [p for p in arvore.values() if p["quantidade_total"] > 0]
    return sorted(resultado, key=lambda x: sort_key(x["codigo"]))


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
