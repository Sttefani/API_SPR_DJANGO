# fichas/filters.py - VERSÃO OTIMIZADA E SIMPLIFICADA

import django_filters
from django import forms
from django.db.models import Q, Count
from .models import FichaLocalCrime


class FichaLocalCrimeFilter(django_filters.FilterSet):
    """
    Filtros otimizados para fichas de local de crime.
    Foco em relatórios práticos e consultas comuns.
    """
    
    # ===== FILTROS DA OCORRÊNCIA PAI =====
    ocorrencia_id = django_filters.NumberFilter(
        field_name='ocorrencia__id',
        label='ID da Ocorrência'
    )
    
    numero_ocorrencia = django_filters.CharFilter(
        field_name='ocorrencia__numero_ocorrencia',
        lookup_expr='icontains',
        label='Número da Ocorrência'
    )
    
    status_ocorrencia = django_filters.ChoiceFilter(
        field_name='ocorrencia__status',
        choices=[
            ('AGUARDANDO_PERITO', 'Aguardando Perito'),
            ('EM_ANALISE', 'Em Análise'),
            ('FINALIZADA', 'Finalizada')
        ],
        label='Status da Ocorrência'
    )
    
    servico_pericial_id = django_filters.NumberFilter(
        field_name='ocorrencia__servico_pericial__id',
        label='ID do Serviço Pericial'
    )
    
    perito_atribuido_id = django_filters.NumberFilter(
        field_name='ocorrencia__perito_atribuido__id',
        label='ID do Perito Atribuído'
    )
    
    perito_nome = django_filters.CharFilter(
        field_name='ocorrencia__perito_atribuido__nome_completo',
        lookup_expr='icontains',
        label='Nome do Perito'
    )
    
    # ===== FILTROS DE DATA =====
    data_fato_de = django_filters.DateFilter(
        field_name='ocorrencia__data_fato',
        lookup_expr='gte',
        label='Data do Fato (de)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    data_fato_ate = django_filters.DateFilter(
        field_name='ocorrencia__data_fato',
        lookup_expr='lte',
        label='Data do Fato (até)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    criada_em_de = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Ficha criada em (de)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    criada_em_ate = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Ficha criada em (até)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    # ===== FILTROS DA FICHA =====
    endereco = django_filters.CharFilter(
        field_name='endereco_completo',
        lookup_expr='icontains',
        label='Endereço'
    )
    
    auxiliar_id = django_filters.NumberFilter(
        field_name='auxiliar_operacional__id',
        label='ID do Auxiliar'
    )
    
    auxiliar_nome = django_filters.CharFilter(
        field_name='auxiliar_operacional__nome_completo',
        lookup_expr='icontains',
        label='Nome do Auxiliar'
    )
    
    # ===== FILTROS BOOLEANOS =====
    local_fechado = django_filters.BooleanFilter(
        label='Local Fechado'
    )
    
    endereco_nao_localizado = django_filters.BooleanFilter(
        label='Endereço Não Localizado'
    )
    
    tem_coordenadas = django_filters.BooleanFilter(
        method='filter_tem_coordenadas',
        label='Tem Coordenadas GPS'
    )
    
    tem_vitimas = django_filters.BooleanFilter(
        method='filter_tem_vitimas',
        label='Tem Vítimas'
    )
    
    tem_vestigios = django_filters.BooleanFilter(
        method='filter_tem_vestigios',
        label='Tem Vestígios'
    )
    
    # ===== FILTROS POR QUANTIDADE =====
    min_vitimas = django_filters.NumberFilter(
        method='filter_min_vitimas',
        label='Mínimo de Vítimas'
    )
    
    max_vitimas = django_filters.NumberFilter(
        method='filter_max_vitimas',
        label='Máximo de Vítimas'
    )
    
    min_vestigios = django_filters.NumberFilter(
        method='filter_min_vestigios',
        label='Mínimo de Vestígios'
    )
    
    max_vestigios = django_filters.NumberFilter(
        method='filter_max_vestigios',
        label='Máximo de Vestígios'
    )
    
    # ===== BUSCA GERAL =====
    busca_geral = django_filters.CharFilter(
        method='filter_busca_geral',
        label='Busca Geral (endereço, observações, vítimas, etc.)'
    )
    
    # ===== ORDENAÇÃO =====
    ordering = django_filters.OrderingFilter(
        fields=(
            ('created_at', 'Data de Criação da Ficha'),
            ('ocorrencia__data_fato', 'Data do Fato'),
            ('ocorrencia__numero_ocorrencia', 'Número da Ocorrência'),
            ('endereco_completo', 'Endereço'),
        )
    )

    class Meta:
        model = FichaLocalCrime
        fields = []

    # ===== MÉTODOS PERSONALIZADOS =====
    def filter_tem_coordenadas(self, queryset, name, value):
        if value is True:
            return queryset.exclude(Q(coordenadas='') | Q(coordenadas__isnull=True))
        elif value is False:
            return queryset.filter(Q(coordenadas='') | Q(coordenadas__isnull=True))
        return queryset

    def filter_tem_vitimas(self, queryset, name, value):
        if value is True:
            return queryset.filter(vitimas__deleted_at__isnull=True).distinct()
        elif value is False:
            return queryset.filter(vitimas__isnull=True)
        return queryset

    def filter_tem_vestigios(self, queryset, name, value):
        if value is True:
            return queryset.filter(vestigios__deleted_at__isnull=True).distinct()
        elif value is False:
            return queryset.filter(vestigios__isnull=True)
        return queryset

    def filter_min_vitimas(self, queryset, name, value):
        if value is not None:
            return queryset.annotate(
                num_vitimas=Count('vitimas', filter=Q(vitimas__deleted_at__isnull=True))
            ).filter(num_vitimas__gte=value)
        return queryset

    def filter_max_vitimas(self, queryset, name, value):
        if value is not None:
            return queryset.annotate(
                num_vitimas=Count('vitimas', filter=Q(vitimas__deleted_at__isnull=True))
            ).filter(num_vitimas__lte=value)
        return queryset

    def filter_min_vestigios(self, queryset, name, value):
        if value is not None:
            return queryset.annotate(
                num_vestigios=Count('vestigios', filter=Q(vestigios__deleted_at__isnull=True))
            ).filter(num_vestigios__gte=value)
        return queryset

    def filter_max_vestigios(self, queryset, name, value):
        if value is not None:
            return queryset.annotate(
                num_vestigios=Count('vestigios', filter=Q(vestigios__deleted_at__isnull=True))
            ).filter(num_vestigios__lte=value)
        return queryset

    def filter_busca_geral(self, queryset, name, value):
        if not value:
            return queryset
        
        return queryset.filter(
            Q(ocorrencia__numero_ocorrencia__icontains=value) |
            Q(endereco_completo__icontains=value) |
            Q(observacoes_local__icontains=value) |
            Q(ocorrencia__historico__icontains=value) |
            Q(ocorrencia__perito_atribuido__nome_completo__icontains=value) |
            Q(auxiliar_operacional__nome_completo__icontains=value) |
            Q(vitimas__nome__icontains=value) |
            Q(vestigios__descricao__icontains=value)
        ).distinct()


# =============================================================================
# EXEMPLOS DE USO DOS FILTROS:
# =============================================================================

"""
FILTROS BÁSICOS:
- ?ocorrencia_id=123                    # Ficha de uma ocorrência específica
- ?status_ocorrencia=FINALIZADA         # Fichas de ocorrências finalizadas
- ?servico_pericial_id=2               # Fichas de um serviço específico

FILTROS DE DATA:
- ?data_fato_de=2025-01-01&data_fato_ate=2025-12-31    # Período do fato
- ?criada_em_de=2025-09-01                             # Fichas criadas a partir de setembro

FILTROS DA FICHA:
- ?local_fechado=true                   # Apenas locais fechados
- ?tem_vitimas=true                     # Apenas fichas com vítimas
- ?min_vestigios=3                      # Fichas com pelo menos 3 vestígios
- ?auxiliar_nome=marcos                 # Fichas com auxiliar específico

BUSCA GERAL:
- ?busca_geral=homicidio                # Busca em vários campos

ORDENAÇÃO:
- ?ordering=-created_at                 # Mais recentes primeiro
- ?ordering=ocorrencia__data_fato       # Por data do fato

COMBINAÇÕES ÚTEIS PARA RELATÓRIOS:
- ?status_ocorrencia=FINALIZADA&tem_vitimas=true&data_fato_de=2025-01-01
- ?perito_nome=silva&local_fechado=true&min_vestigios=2
- ?busca_geral=centro&tem_coordenadas=true&ordering=-created_at
"""