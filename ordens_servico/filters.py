# ordens_servico/filters.py

import django_filters
from django.db.models import Q
from .models import OrdemServico


class OrdemServicoFilter(django_filters.FilterSet):
    """
    Filtros avançados para Ordens de Serviço.
    
    Exemplos de uso:
    - ?status=ABERTA
    - ?vencida=true
    - ?sem_ciencia=true
    - ?urgencia=vermelho
    - ?perito_id=5
    - ?data_inicio=2025-01-01&data_fim=2025-12-31
    - ?search=0001/2025
    """
    
    # Filtro por texto (número da OS ou ocorrência)
    search = django_filters.CharFilter(
        method='filter_search',
        label='Busca',
        help_text='Busca por número da OS ou número da ocorrência'
    )
    
    # Filtro por status
    status = django_filters.ChoiceFilter(
        choices=OrdemServico.Status.choices,
        label='Status'
    )
    
    # Filtro por perito destinatário
    perito_id = django_filters.NumberFilter(
        field_name='ocorrencia__perito_atribuido__id',
        label='Perito Destinatário'
    )
    
    # Filtro por período de emissão
    data_inicio = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__gte',
        label='Emitida a partir de'
    )
    
    data_fim = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__lte',
        label='Emitida até'
    )
    
    # Filtros booleanos
    vencida = django_filters.BooleanFilter(
        method='filter_vencida',
        label='Apenas Vencidas'
    )
    
    sem_ciencia = django_filters.BooleanFilter(
        method='filter_sem_ciencia',
        label='Sem Ciência'
    )
    
    com_justificativa = django_filters.BooleanFilter(
        method='filter_com_justificativa',
        label='Com Justificativa de Atraso'
    )
    
    # Filtro por urgência
    urgencia = django_filters.ChoiceFilter(
        method='filter_urgencia',
        choices=[
            ('verde', 'Verde (5+ dias)'),
            ('amarelo', 'Amarelo (3-4 dias)'),
            ('laranja', 'Laranja (1-2 dias)'),
            ('vermelho', 'Vermelho (Vencida)'),
            ('concluida', 'Concluída'),
        ],
        label='Urgência'
    )
    
    # Filtro por número de reiteração
    apenas_originais = django_filters.BooleanFilter(
        method='filter_apenas_originais',
        label='Apenas OS Originais'
    )
    
    apenas_reiteracoes = django_filters.BooleanFilter(
        method='filter_apenas_reiteracoes',
        label='Apenas Reiterações'
    )
    
    class Meta:
        model = OrdemServico
        fields = [
            'status',
            'perito_id',
            'data_inicio',
            'data_fim',
            'vencida',
            'sem_ciencia',
            'com_justificativa',
            'urgencia',
            'apenas_originais',
            'apenas_reiteracoes',
            'search'
        ]
    
    def filter_search(self, queryset, name, value):
        """
        Busca por número da OS ou número da ocorrência.
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(numero_os__icontains=value) |
            Q(ocorrencia__numero_ocorrencia__icontains=value)
        )
    
    def filter_vencida(self, queryset, name, value):
        """
        Filtra OS vencidas.
        Usa lógica customizada porque é propriedade calculada.
        """
        if value is None:
            return queryset
        
        if value:
            # Retorna apenas vencidas
            return queryset.filter(
                status__in=[
                    OrdemServico.Status.ABERTA,
                    OrdemServico.Status.EM_ANDAMENTO,
                    OrdemServico.Status.VENCIDA
                ],
                data_ciencia__isnull=False
            ).exclude(
                status=OrdemServico.Status.CONCLUIDA
            )
        else:
            # Retorna apenas não-vencidas
            return queryset.filter(
                Q(status=OrdemServico.Status.AGUARDANDO_CIENCIA) |
                Q(status=OrdemServico.Status.CONCLUIDA) |
                Q(data_ciencia__isnull=True)
            )
    
    def filter_sem_ciencia(self, queryset, name, value):
        """
        Filtra OS que ainda não tiveram ciência.
        """
        if value is None:
            return queryset
        
        if value:
            return queryset.filter(ciente_por__isnull=True)
        else:
            return queryset.filter(ciente_por__isnull=False)
    
    def filter_com_justificativa(self, queryset, name, value):
        """
        Filtra OS que têm justificativa de atraso.
        """
        if value is None:
            return queryset
        
        if value:
            return queryset.exclude(justificativa_atraso='')
        else:
            return queryset.filter(justificativa_atraso='')
    
    def filter_urgencia(self, queryset, name, value):
        """
        Filtra por nível de urgência.
        Este filtro é aproximado porque urgência é propriedade calculada.
        """
        if not value:
            return queryset
        
        from django.utils import timezone
        from datetime import timedelta
        
        hoje = timezone.now()
        
        if value == 'concluida':
            return queryset.filter(status=OrdemServico.Status.CONCLUIDA)
        
        elif value == 'vermelho':
            # Vencida ou vence hoje
            return queryset.filter(
                data_ciencia__isnull=False,
                status__in=[
                    OrdemServico.Status.ABERTA,
                    OrdemServico.Status.EM_ANDAMENTO,
                    OrdemServico.Status.VENCIDA
                ]
            )
        
        elif value == 'laranja':
            # 1-2 dias restantes
            return queryset.filter(
                data_ciencia__isnull=False,
                status__in=[
                    OrdemServico.Status.ABERTA,
                    OrdemServico.Status.EM_ANDAMENTO
                ]
            )
        
        elif value == 'amarelo':
            # 3-4 dias restantes
            return queryset.filter(
                data_ciencia__isnull=False,
                status__in=[
                    OrdemServico.Status.ABERTA,
                    OrdemServico.Status.EM_ANDAMENTO
                ]
            )
        
        elif value == 'verde':
            # 5+ dias restantes
            return queryset.filter(
                data_ciencia__isnull=False,
                status__in=[
                    OrdemServico.Status.ABERTA,
                    OrdemServico.Status.EM_ANDAMENTO
                ]
            )
        
        return queryset
    
    def filter_apenas_originais(self, queryset, name, value):
        """
        Filtra apenas OS originais (não-reiterações).
        """
        if value is None:
            return queryset
        
        if value:
            return queryset.filter(numero_reiteracao=0)
        
        return queryset
    
    def filter_apenas_reiteracoes(self, queryset, name, value):
        """
        Filtra apenas reiterações (não-originais).
        """
        if value is None:
            return queryset
        
        if value:
            return queryset.filter(numero_reiteracao__gt=0)
        
        return queryset