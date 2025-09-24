# ordens_servico/filters.py

import django_filters
from django import forms
from django.utils import timezone
from .models import OrdemServico

class OrdemServicoFilter(django_filters.FilterSet):
    """
    Filtros para o modelo OrdemServico, permitindo buscas detalhadas.
    """
    # =============================================================================
    # FILTROS PELA OCORRÊNCIA PAI
    # =============================================================================
    numero_ocorrencia = django_filters.CharFilter(
        field_name='ocorrencia__numero_ocorrencia',
        lookup_expr='icontains',
        label='Número da Ocorrência'
    )

    perito_destinatario = django_filters.CharFilter(
        field_name='ocorrencia__perito_atribuido__nome_completo',
        lookup_expr='icontains',
        label='Nome do Perito Destinatário'
    )
    
    servico_pericial = django_filters.CharFilter(
        field_name='ocorrencia__servico_pericial__nome',
        lookup_expr='icontains',
        label='Nome do Serviço Pericial'
    )

    # =============================================================================
    # FILTROS DA PRÓPRIA ORDEM DE SERVIÇO
    # =============================================================================
    numero_os = django_filters.CharFilter(
        field_name='numero_os',
        lookup_expr='icontains',
        label='Número da Ordem de Serviço'
    )
    
    status = django_filters.ChoiceFilter(
        choices=OrdemServico.Status.choices,
        label='Status da OS'
    )

    # Filtro por período de data de EMISSÃO
    emitida_de = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__gte',
        label='Emitida em (de)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    emitida_ate = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__lte',
        label='Emitida em (até)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    # Filtro customizado para VENCIDAS
    vencida = django_filters.BooleanFilter(
        method='filter_vencida',
        label='Apenas OS Vencidas'
    )

    class Meta:
        model = OrdemServico
        fields = [
            'numero_ocorrencia', 'perito_destinatario', 'servico_pericial',
            'numero_os', 'status'
        ]

    def filter_vencida(self, queryset, name, value):
        if value is True:
            # Retorna OS abertas ou aguardando ciência cuja data de vencimento já passou
            return queryset.filter(
                status__in=['ABERTA', 'AGUARDANDO_CIENCIA'],
                data_vencimento__lt=timezone.now()
            )
        elif value is False:
            # Retorna OS que não estão vencidas
            return queryset.exclude(
                status__in=['ABERTA', 'AGUARDANDO_CIENCIA'],
                data_vencimento__lt=timezone.now()
            )
        return queryset