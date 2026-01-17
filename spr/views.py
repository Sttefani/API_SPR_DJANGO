# ==========================================
# SPR/VIEWS.PY - ANÁLISE CRIMINAL
# ==========================================
# Versão corrigida - Cards dinâmicos baseados no banco
#
# Contém:
# 1. EstatisticasCriminaisView (original)
# 2. OcorrenciasGeoView (original)
# 3. DashboardCriminalView (CORRIGIDA - dinâmica)
# ==========================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Value, CharField, Case, When
from django.db.models.functions import TruncMonth, Coalesce, ExtractWeekDay, ExtractHour

from ocorrencias.endereco_models import EnderecoOcorrencia
from ocorrencias.models import Ocorrencia
from classificacoes.models import ClassificacaoOcorrencia


# ==========================================
# 1. ESTATÍSTICAS CRIMINAIS (ORIGINAL)
# ==========================================
class EstatisticasCriminaisView(APIView):
    """
    View Legada/Geral: Retorna estatísticas agregadas.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. FILTROS
        data_inicio = request.GET.get("data_inicio") or None
        data_fim = request.GET.get("data_fim") or None
        classificacao_id = request.GET.get("classificacao_id")
        cidade_id = request.GET.get("cidade_id")
        bairro = request.GET.get("bairro") or None

        def safe_int(val):
            try:
                return int(val) if val not in ["null", "", None] else None
            except:
                return None

        classificacao_id = safe_int(classificacao_id)
        cidade_id = safe_int(cidade_id)

        queryset = Ocorrencia.objects.all()

        if data_inicio:
            queryset = queryset.filter(data_fato__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_fato__lte=data_fim)

        # LÓGICA DE HIERARQUIA (PAI + FILHAS)
        if classificacao_id:
            ids_filhas = ClassificacaoOcorrencia.objects.filter(
                parent_id=classificacao_id
            ).values_list("id", flat=True)
            ids_totais = [classificacao_id] + list(ids_filhas)
            queryset = queryset.filter(classificacao_id__in=ids_totais)

        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)
        if bairro:
            queryset = queryset.filter(
                Q(endereco__bairro_legado__icontains=bairro)
                | Q(endereco__bairro_novo__nome__icontains=bairro)
            )

        total_ocorrencias = queryset.count()

        # Agregações
        por_classificacao = (
            queryset.values("classificacao__codigo", "classificacao__nome")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        por_cidade = (
            queryset.values("cidade__nome")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        por_bairro = (
            EnderecoOcorrencia.objects.filter(ocorrencia__in=queryset, tipo="EXTERNA")
            .annotate(
                bairro_final=Coalesce(
                    "bairro_novo__nome", "bairro_legado", output_field=CharField()
                )
            )
            .filter(bairro_final__isnull=False)
            .exclude(bairro_final="")
            .values("bairro_final")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        por_mes = (
            queryset.filter(data_fato__isnull=False)
            .annotate(mes=TruncMonth("data_fato"))
            .values("mes")
            .annotate(quantidade=Count("id"))
            .order_by("mes")
        )

        return Response(
            {
                "total_ocorrencias": total_ocorrencias,
                "por_classificacao": [
                    {
                        "classificacao": f"{i['classificacao__codigo']} - {i['classificacao__nome']}",
                        "quantidade": i["quantidade"],
                    }
                    for i in por_classificacao
                ],
                "por_cidade": [
                    {
                        "cidade": i["cidade__nome"] or "Sem cidade",
                        "quantidade": i["quantidade"],
                    }
                    for i in por_cidade
                ],
                "por_bairro": [
                    {"bairro": i["bairro_final"], "quantidade": i["quantidade"]}
                    for i in por_bairro
                ],
                "por_mes": [
                    {
                        "mes": i["mes"].strftime("%Y-%m") if i["mes"] else "",
                        "quantidade": i["quantidade"],
                    }
                    for i in por_mes
                ],
            }
        )


# ==========================================
# 2. OCORRÊNCIAS GEO (ORIGINAL)
# ==========================================
class OcorrenciasGeoView(APIView):
    """Retorna ocorrências com coordenadas para o mapa"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data_inicio = request.GET.get("data_inicio")
        data_fim = request.GET.get("data_fim")
        classificacao_id = request.GET.get("classificacao_id")
        cidade_id = request.GET.get("cidade_id")
        bairro = request.GET.get("bairro")

        def safe_int(val):
            try:
                return int(val) if val not in ["null", "", None] else None
            except:
                return None

        classificacao_id = safe_int(classificacao_id)
        cidade_id = safe_int(cidade_id)

        queryset = Ocorrencia.objects.filter(
            endereco__latitude__isnull=False,
            endereco__longitude__isnull=False,
            endereco__tipo="EXTERNA",
        ).select_related("classificacao", "cidade", "endereco", "endereco__bairro_novo")

        if data_inicio:
            queryset = queryset.filter(data_fato__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_fato__lte=data_fim)

        # LÓGICA DE HIERARQUIA NO MAPA
        if classificacao_id:
            ids_filhas = ClassificacaoOcorrencia.objects.filter(
                parent_id=classificacao_id
            ).values_list("id", flat=True)
            ids_totais = [classificacao_id] + list(ids_filhas)
            queryset = queryset.filter(classificacao_id__in=ids_totais)

        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)
        if bairro:
            queryset = queryset.filter(
                Q(endereco__bairro_legado__icontains=bairro)
                | Q(endereco__bairro_novo__nome__icontains=bairro)
            )

        queryset = queryset[:5000]
        data = []
        for o in queryset:
            data.append(
                {
                    "id": o.id,
                    "numero_ocorrencia": o.numero_ocorrencia,
                    "classificacao": {
                        "codigo": o.classificacao.codigo if o.classificacao else "",
                        "nome": (
                            o.classificacao.nome
                            if o.classificacao
                            else "Sem classificação"
                        ),
                    },
                    "endereco": {
                        "latitude": o.endereco.latitude,
                        "longitude": o.endereco.longitude,
                        "bairro": o.endereco.nome_bairro,
                        "logradouro": o.endereco.logradouro or "",
                    },
                    "data_fato": (
                        o.data_fato.strftime("%d/%m/%Y") if o.data_fato else ""
                    ),
                    "cidade": {"nome": o.cidade.nome if o.cidade else ""},
                }
            )
        return Response(data)


# ==========================================
# 3. DASHBOARD CRIMINAL (CORRIGIDA - DINÂMICA)
# ==========================================
class DashboardCriminalView(APIView):
    """
    Dashboard com KPIs dinâmicos baseados na hierarquia do banco.

    Regras:
    - PAI (parent=null): Agregador - soma das quantidades das filhas
    - FILHA (parent=PAI): Quantidade individual
    - Filtros: cidade, bairro, classificação, data
    - Dados 100% do banco, nada hardcoded
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ==========================================
        # 1. EXTRAÇÃO DE FILTROS
        # ==========================================
        data_inicio = request.GET.get("data_inicio")
        data_fim = request.GET.get("data_fim")
        classificacao_id = request.GET.get("classificacao_id")
        cidade_id = request.GET.get("cidade_id")
        bairro = request.GET.get("bairro")

        def safe_int(val):
            try:
                return int(val) if val not in ["null", "", None] else None
            except:
                return None

        classificacao_id = safe_int(classificacao_id)
        cidade_id = safe_int(cidade_id)

        # ==========================================
        # 2. QUERYSET BASE COM FILTROS
        # ==========================================
        queryset = Ocorrencia.objects.all()

        if data_inicio:
            queryset = queryset.filter(data_fato__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_fato__lte=data_fim)

        # Filtro hierárquico de classificação
        if classificacao_id:
            ids_filhas = ClassificacaoOcorrencia.objects.filter(
                parent_id=classificacao_id
            ).values_list("id", flat=True)
            ids_totais = [classificacao_id] + list(ids_filhas)
            queryset = queryset.filter(classificacao_id__in=ids_totais)

        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)

        if bairro:
            queryset = queryset.filter(
                Q(endereco__bairro_legado__icontains=bairro)
                | Q(endereco__bairro_novo__nome__icontains=bairro)
            )

        # ==========================================
        # 3. CARDS DINÂMICOS (PAI = SOMA DAS FILHAS)
        # ==========================================
        total_geral = queryset.count()
        total_cidades = queryset.values("cidade").distinct().count()

        # Buscar todos os PAIs (parent=null) ordenados por código
        pais = ClassificacaoOcorrencia.objects.filter(parent__isnull=True).order_by(
            "codigo"
        )

        cards = []

        for pai in pais:
            # Buscar todas as filhas deste pai
            filhas = ClassificacaoOcorrencia.objects.filter(parent=pai)
            ids_filhas = list(filhas.values_list("id", flat=True))

            # Calcular quantidade do PAI (soma das filhas)
            # Regra: PAI nunca é classificado diretamente, só as filhas
            if ids_filhas:
                quantidade_pai = queryset.filter(
                    classificacao_id__in=ids_filhas
                ).count()
            else:
                # Caso raro: PAI sem filhas cadastradas
                quantidade_pai = 0

            # Pular PAIs sem ocorrências no período/filtro
            if quantidade_pai == 0:
                continue

            # Percentual em relação ao total
            percentual = (
                round((quantidade_pai / total_geral) * 100, 1) if total_geral > 0 else 0
            )

            # Montar detalhamento das filhas (drill-down)
            filhas_detalhe = []
            for filha in filhas.order_by("codigo"):
                quantidade_filha = queryset.filter(classificacao_id=filha.id).count()

                if quantidade_filha > 0:
                    percentual_filha = (
                        round((quantidade_filha / quantidade_pai) * 100, 1)
                        if quantidade_pai > 0
                        else 0
                    )

                    filhas_detalhe.append(
                        {
                            "id": filha.id,
                            "codigo": filha.codigo,
                            "nome": filha.nome,
                            "quantidade": quantidade_filha,
                            "percentual": percentual_filha,
                        }
                    )

            # Ordenar filhas por quantidade (maior primeiro)
            filhas_detalhe.sort(key=lambda x: x["quantidade"], reverse=True)

            # Adicionar card do PAI
            cards.append(
                {
                    "id": pai.id,
                    "codigo": pai.codigo,
                    "nome": pai.nome,
                    "quantidade": quantidade_pai,
                    "percentual": percentual,
                    "filhas": filhas_detalhe,
                }
            )

        # Ordenar cards por quantidade (maior primeiro)
        cards.sort(key=lambda x: x["quantidade"], reverse=True)

        # ==========================================
        # 4. GRÁFICOS
        # ==========================================

        # Por classificação (top 10)
        por_classificacao = (
            queryset.values("classificacao__codigo", "classificacao__nome")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        # Por cidade (top 10)
        por_cidade = (
            queryset.values("cidade__nome")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        # Por bairro (top 10)
        por_bairro = (
            EnderecoOcorrencia.objects.filter(ocorrencia__in=queryset, tipo="EXTERNA")
            .annotate(
                bairro_final=Coalesce(
                    "bairro_novo__nome", "bairro_legado", output_field=CharField()
                )
            )
            .filter(bairro_final__isnull=False)
            .exclude(bairro_final="")
            .values("bairro_final")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        # Por mês
        por_mes = (
            queryset.filter(data_fato__isnull=False)
            .annotate(mes=TruncMonth("data_fato"))
            .values("mes")
            .annotate(quantidade=Count("id"))
            .order_by("mes")
        )

        # Por dia da semana
        dias_map = {
            1: "Domingo",
            2: "Segunda",
            3: "Terça",
            4: "Quarta",
            5: "Quinta",
            6: "Sexta",
            7: "Sábado",
        }

        por_dia_semana_raw = (
            queryset.filter(data_fato__isnull=False)
            .annotate(dia_semana=ExtractWeekDay("data_fato"))
            .values("dia_semana")
            .annotate(quantidade=Count("id"))
            .order_by("dia_semana")
        )

        por_dia_semana = [
            {
                "dia": dias_map.get(i["dia_semana"], "N/A"),
                "dia_numero": i["dia_semana"],
                "quantidade": i["quantidade"],
            }
            for i in por_dia_semana_raw
        ]

        # Por turno e matriz dia x turno
        por_turno = []
        matriz_dia_turno = []

        if hasattr(Ocorrencia, "hora_fato"):
            # Por turno
            por_turno_raw = (
                queryset.filter(hora_fato__isnull=False)
                .annotate(hora=ExtractHour("hora_fato"))
                .annotate(
                    turno=Case(
                        When(
                            hora__gte=0, hora__lt=6, then=Value("Madrugada (00h-06h)")
                        ),
                        When(hora__gte=6, hora__lt=12, then=Value("Manhã (06h-12h)")),
                        When(hora__gte=12, hora__lt=18, then=Value("Tarde (12h-18h)")),
                        When(hora__gte=18, hora__lt=24, then=Value("Noite (18h-00h)")),
                        default=Value("Não informado"),
                        output_field=CharField(),
                    )
                )
                .values("turno")
                .annotate(quantidade=Count("id"))
                .order_by("turno")
            )

            por_turno = [
                {"turno": i["turno"], "quantidade": i["quantidade"]}
                for i in por_turno_raw
            ]

            # Matriz dia x turno (para heatmap)
            matriz_raw = (
                queryset.filter(data_fato__isnull=False, hora_fato__isnull=False)
                .annotate(
                    dia_semana=ExtractWeekDay("data_fato"),
                    hora=ExtractHour("hora_fato"),
                )
                .annotate(
                    turno=Case(
                        When(hora__gte=0, hora__lt=4, then=Value("00h-04h")),
                        When(hora__gte=4, hora__lt=8, then=Value("04h-08h")),
                        When(hora__gte=8, hora__lt=12, then=Value("08h-12h")),
                        When(hora__gte=12, hora__lt=16, then=Value("12h-16h")),
                        When(hora__gte=16, hora__lt=20, then=Value("16h-20h")),
                        When(hora__gte=20, hora__lt=24, then=Value("20h-00h")),
                        default=Value("N/A"),
                        output_field=CharField(),
                    )
                )
                .values("dia_semana", "turno")
                .annotate(quantidade=Count("id"))
                .order_by("dia_semana", "turno")
            )

            matriz_dia_turno = [
                {
                    "dia": dias_map.get(i["dia_semana"], "N/A"),
                    "dia_numero": i["dia_semana"],
                    "turno": i["turno"],
                    "quantidade": i["quantidade"],
                }
                for i in matriz_raw
            ]

        # ==========================================
        # 5. RESPOSTA FINAL
        # ==========================================
        return Response(
            {
                "resumo": {
                    "total_ocorrencias": total_geral,
                    "total_cidades": total_cidades,
                    "total_categorias": len(cards),
                },
                "cards": cards,
                "graficos": {
                    "por_classificacao": [
                        {
                            "codigo": i["classificacao__codigo"] or "",
                            "nome": i["classificacao__nome"] or "N/I",
                            "quantidade": i["quantidade"],
                        }
                        for i in por_classificacao
                    ],
                    "por_cidade": [
                        {
                            "cidade": i["cidade__nome"] or "Sem cidade",
                            "quantidade": i["quantidade"],
                        }
                        for i in por_cidade
                    ],
                    "por_bairro": [
                        {"bairro": i["bairro_final"], "quantidade": i["quantidade"]}
                        for i in por_bairro
                    ],
                    "por_mes": [
                        {
                            "mes": i["mes"].strftime("%Y-%m") if i["mes"] else "",
                            "mes_nome": i["mes"].strftime("%b/%Y") if i["mes"] else "",
                            "quantidade": i["quantidade"],
                        }
                        for i in por_mes
                    ],
                    "por_dia_semana": por_dia_semana,
                    "por_turno": por_turno,
                    "matriz_dia_turno": matriz_dia_turno,
                },
            }
        )
