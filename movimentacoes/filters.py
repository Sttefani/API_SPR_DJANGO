# movimentacoes/filters.py

import django_filters
from django import forms
from django.db.models import Q
from .models import Movimentacao


class MovimentacaoFilter(django_filters.FilterSet):
    """
    Filtros para o modelo Movimentacao, permitindo buscas detalhadas no "extrato".
    """
    # FILTRO ADICIONADO PARA BUSCAR PELA OCORRÊNCIA
    ocorrencia = django_filters.CharFilter(
        field_name='ocorrencia__numero_ocorrencia',
        lookup_expr='icontains',
        label='Número da Ocorrência'
    )

    # Filtro de data (período)
    data_de = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__gte', # gte = Greater Than or Equal (maior ou igual a)
        label='Movimentações de (data)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    data_ate = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__lte', # lte = Less Than or Equal (menor ou igual a)
        label='Movimentações até (data)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    # Filtro textual para buscar no assunto ou na descrição
    busca_texto = django_filters.CharFilter(
        method='filter_busca_texto',
        label='Buscar em Assunto/Descrição'
    )

    # Filtro pelo nome do usuário que criou a movimentação
    usuario = django_filters.CharFilter(
        field_name='created_by__nome_completo',
        lookup_expr='icontains',
        label='Movimentado por (nome)'
    )
    
    class Meta:
        model = Movimentacao
        # Adiciona o novo filtro à lista
        fields = ['ocorrencia', 'usuario', 'data_de', 'data_ate']

    def filter_busca_texto(self, queryset, name, value):
        """
        Método customizado para a busca textual em múltiplos campos.
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(assunto__icontains=value) | Q(descricao__icontains=value)
        ).distinct()