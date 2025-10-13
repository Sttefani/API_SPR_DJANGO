# ==========================================
# ✅ VIEWS DE ANÁLISE CRIMINAL
# ==========================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from django.db.models.functions import TruncMonth

from ocorrencias.endereco_models import EnderecoOcorrencia
from ocorrencias.models import Ocorrencia


class EstatisticasCriminaisView(APIView):
    """Retorna estatísticas agregadas de ocorrências"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # ✅ CORREÇÃO: Pegar e validar filtros corretamente
        data_inicio = request.GET.get('data_inicio') or None
        data_fim = request.GET.get('data_fim') or None
        classificacao_id = request.GET.get('classificacao_id')
        cidade_id = request.GET.get('cidade_id')
        bairro = request.GET.get('bairro') or None
        
        # ✅ CORREÇÃO: Converter 'null' string para None
        if classificacao_id in ['null', '', None]:
            classificacao_id = None
        else:
            try:
                classificacao_id = int(classificacao_id)
            except (ValueError, TypeError):
                classificacao_id = None
        
        if cidade_id in ['null', '', None]:
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
        if bairro:
            queryset = queryset.filter(endereco__bairro__icontains=bairro)
        
        total_ocorrencias = queryset.count()
        
        # Por classificação
        por_classificacao = queryset.values(
            'classificacao__codigo',
            'classificacao__nome'
        ).annotate(quantidade=Count('id')).order_by('-quantidade')[:10]
        
        # Por cidade
        por_cidade = queryset.values(
            'cidade__nome'
        ).annotate(quantidade=Count('id')).order_by('-quantidade')[:10]
        
        # Por bairro
        por_bairro = EnderecoOcorrencia.objects.filter(
            ocorrencia__in=queryset,
            tipo='EXTERNA',
            bairro__isnull=False
        ).exclude(bairro='').values('bairro').annotate(
            quantidade=Count('id')
        ).order_by('-quantidade')[:10]
        
        # Por mês
        por_mes = queryset.filter(
            data_fato__isnull=False
        ).annotate(
            mes=TruncMonth('data_fato')
        ).values('mes').annotate(quantidade=Count('id')).order_by('mes')
        
        return Response({
            'total_ocorrencias': total_ocorrencias,
            'por_classificacao': [
                {
                    'classificacao': f"{item['classificacao__codigo']} - {item['classificacao__nome']}",
                    'quantidade': item['quantidade']
                }
                for item in por_classificacao
            ],
            'por_cidade': [
                {
                    'cidade': item['cidade__nome'] or 'Sem cidade',
                    'quantidade': item['quantidade']
                }
                for item in por_cidade
            ],
            'por_bairro': list(por_bairro),
            'por_mes': [
                {
                    'mes': item['mes'].strftime('%Y-%m') if item['mes'] else '',
                    'quantidade': item['quantidade']
                }
                for item in por_mes
            ]
        })


class OcorrenciasGeoView(APIView):
    """Retorna ocorrências com coordenadas para o mapa"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # ✅ CORREÇÃO: Pegar e validar filtros corretamente
        data_inicio = request.GET.get('data_inicio') or None
        data_fim = request.GET.get('data_fim') or None
        classificacao_id = request.GET.get('classificacao_id')
        cidade_id = request.GET.get('cidade_id')
        bairro = request.GET.get('bairro') or None
        
        # ✅ CORREÇÃO: Converter 'null' string para None
        if classificacao_id in ['null', '', None]:
            classificacao_id = None
        else:
            try:
                classificacao_id = int(classificacao_id)
            except (ValueError, TypeError):
                classificacao_id = None
        
        if cidade_id in ['null', '', None]:
            cidade_id = None
        else:
            try:
                cidade_id = int(cidade_id)
            except (ValueError, TypeError):
                cidade_id = None
        
        queryset = Ocorrencia.objects.filter(
            endereco__latitude__isnull=False,
            endereco__longitude__isnull=False,
            endereco__tipo='EXTERNA'
        ).select_related('classificacao', 'cidade', 'endereco')
        
        # Aplicar filtros apenas se tiver valor válido
        if data_inicio:
            queryset = queryset.filter(data_fato__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_fato__lte=data_fim)
        if classificacao_id:
            queryset = queryset.filter(classificacao_id=classificacao_id)
        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)
        if bairro:
            queryset = queryset.filter(endereco__bairro__icontains=bairro)
        
        queryset = queryset[:5000]
        
        data = []
        for ocorrencia in queryset:
            data.append({
                'id': ocorrencia.id,
                'numero_ocorrencia': ocorrencia.numero_ocorrencia,
                'classificacao': {
                    'codigo': ocorrencia.classificacao.codigo if ocorrencia.classificacao else '',
                    'nome': ocorrencia.classificacao.nome if ocorrencia.classificacao else 'Sem classificação'
                },
                'endereco': {
                    'latitude': ocorrencia.endereco.latitude,
                    'longitude': ocorrencia.endereco.longitude,
                    'bairro': ocorrencia.endereco.bairro or '',
                    'logradouro': ocorrencia.endereco.logradouro or ''
                },
                'data_fato': ocorrencia.data_fato.strftime('%d/%m/%Y') if ocorrencia.data_fato else '',
                'cidade': {
                    'nome': ocorrencia.cidade.nome if ocorrencia.cidade else ''
                }
            })
        
        return Response(data)