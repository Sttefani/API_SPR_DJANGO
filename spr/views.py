# ==========================================
# ✅ VIEWS DE ANÁLISE CRIMINAL - CORRIGIDO
# ==========================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Value, CharField
from django.db.models.functions import TruncMonth, Coalesce

from ocorrencias.endereco_models import EnderecoOcorrencia
from ocorrencias.models import Ocorrencia


class EstatisticasCriminaisView(APIView):
    """Retorna estatísticas agregadas de ocorrências"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Pegar e validar filtros corretamente
        data_inicio = request.GET.get("data_inicio") or None
        data_fim = request.GET.get("data_fim") or None
        classificacao_id = request.GET.get("classificacao_id")
        cidade_id = request.GET.get("cidade_id")
        bairro = request.GET.get("bairro") or None

        # Converter 'null' string para None
        if classificacao_id in ["null", "", None]:
            classificacao_id = None
        else:
            try:
                classificacao_id = int(classificacao_id)
            except (ValueError, TypeError):
                classificacao_id = None

        if cidade_id in ["null", "", None]:
            cidade_id = None
        else:
            try:
                cidade_id = int(cidade_id)
            except (ValueError, TypeError):
                cidade_id = None

        queryset = Ocorrencia.objects.all()

        # Aplicar filtros apenas se tiver valor válido
        if data_inicio:
            queryset = queryset.filter(data_fato__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_fato__lte=data_fim)
        if classificacao_id:
            queryset = queryset.filter(classificacao_id=classificacao_id)
        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)

        # ✅ CORREÇÃO 1: Filtro Híbrido (Legado ou Novo)
        if bairro:
            queryset = queryset.filter(
                Q(endereco__bairro_legado__icontains=bairro)
                | Q(endereco__bairro_novo__nome__icontains=bairro)
            )

        total_ocorrencias = queryset.count()

        # Por classificação
        por_classificacao = (
            queryset.values("classificacao__codigo", "classificacao__nome")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        # Por cidade
        por_cidade = (
            queryset.values("cidade__nome")
            .annotate(quantidade=Count("id"))
            .order_by("-quantidade")[:10]
        )

        # ✅ CORREÇÃO 2: Agrupamento Híbrido com Coalesce
        # Cria um campo virtual 'bairro_final' juntando as duas tabelas
        por_bairro = (
            EnderecoOcorrencia.objects.filter(ocorrencia__in=queryset, tipo="EXTERNA")
            .annotate(
                bairro_final=Coalesce(
                    "bairro_novo__nome",  # Tenta o nome do cadastro novo
                    "bairro_legado",  # Se falhar, pega o texto antigo
                    output_field=CharField(),
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

        # Montagem da resposta (ajustado para ler bairro_final)
        return Response(
            {
                "total_ocorrencias": total_ocorrencias,
                "por_classificacao": [
                    {
                        "classificacao": f"{item['classificacao__codigo']} - {item['classificacao__nome']}",
                        "quantidade": item["quantidade"],
                    }
                    for item in por_classificacao
                ],
                "por_cidade": [
                    {
                        "cidade": item["cidade__nome"] or "Sem cidade",
                        "quantidade": item["quantidade"],
                    }
                    for item in por_cidade
                ],
                "por_bairro": [
                    {
                        "bairro": item["bairro_final"],  # Lê o campo virtual criado
                        "quantidade": item["quantidade"],
                    }
                    for item in por_bairro
                ],
                "por_mes": [
                    {
                        "mes": item["mes"].strftime("%Y-%m") if item["mes"] else "",
                        "quantidade": item["quantidade"],
                    }
                    for item in por_mes
                ],
            }
        )


class OcorrenciasGeoView(APIView):
    """Retorna ocorrências com coordenadas para o mapa"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Pegar e validar filtros corretamente
        data_inicio = request.GET.get("data_inicio") or None
        data_fim = request.GET.get("data_fim") or None
        classificacao_id = request.GET.get("classificacao_id")
        cidade_id = request.GET.get("cidade_id")
        bairro = request.GET.get("bairro") or None

        # Converter 'null' string para None
        if classificacao_id in ["null", "", None]:
            classificacao_id = None
        else:
            try:
                classificacao_id = int(classificacao_id)
            except (ValueError, TypeError):
                classificacao_id = None

        if cidade_id in ["null", "", None]:
            cidade_id = None
        else:
            try:
                cidade_id = int(cidade_id)
            except (ValueError, TypeError):
                cidade_id = None

        # Otimização: select_related para evitar queries N+1
        queryset = Ocorrencia.objects.filter(
            endereco__latitude__isnull=False,
            endereco__longitude__isnull=False,
            endereco__tipo="EXTERNA",
        ).select_related("classificacao", "cidade", "endereco", "endereco__bairro_novo")

        # Aplicar filtros apenas se tiver valor válido
        if data_inicio:
            queryset = queryset.filter(data_fato__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_fato__lte=data_fim)
        if classificacao_id:
            queryset = queryset.filter(classificacao_id=classificacao_id)
        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)

        # ✅ CORREÇÃO 3: Filtro Híbrido no Mapa
        if bairro:
            queryset = queryset.filter(
                Q(endereco__bairro_legado__icontains=bairro)
                | Q(endereco__bairro_novo__nome__icontains=bairro)
            )

        queryset = queryset[:5000]

        data = []
        for ocorrencia in queryset:
            data.append(
                {
                    "id": ocorrencia.id,
                    "numero_ocorrencia": ocorrencia.numero_ocorrencia,
                    "classificacao": {
                        "codigo": (
                            ocorrencia.classificacao.codigo
                            if ocorrencia.classificacao
                            else ""
                        ),
                        "nome": (
                            ocorrencia.classificacao.nome
                            if ocorrencia.classificacao
                            else "Sem classificação"
                        ),
                    },
                    "endereco": {
                        "latitude": ocorrencia.endereco.latitude,
                        "longitude": ocorrencia.endereco.longitude,
                        # ✅ CORREÇÃO 4: Uso da property segura 'nome_bairro'
                        "bairro": ocorrencia.endereco.nome_bairro,
                        "logradouro": ocorrencia.endereco.logradouro or "",
                    },
                    "data_fato": (
                        ocorrencia.data_fato.strftime("%d/%m/%Y")
                        if ocorrencia.data_fato
                        else ""
                    ),
                    "cidade": {
                        "nome": ocorrencia.cidade.nome if ocorrencia.cidade else ""
                    },
                }
            )

        return Response(data)
