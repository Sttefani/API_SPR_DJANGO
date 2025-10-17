# ordens_servico/filters.py

import django_filters
from django.db.models import Q, F, ExpressionWrapper, DateTimeField
from django.utils import timezone
from datetime import timedelta
from .models import OrdemServico


class OrdemServicoFilter(django_filters.FilterSet):
    
    # ===== FILTROS DE BUSCA =====
    numero_ocorrencia_exato = django_filters.CharFilter(
        field_name='ocorrencia__numero_ocorrencia',
        lookup_expr='exact',
        label='Busca Exata por Número de Ocorrência'
    )
    
    numero_os_exato = django_filters.CharFilter(
        field_name='numero_os',
        lookup_expr='exact',
        label='Busca Exata por Número da OS'
    )
    
    search = django_filters.CharFilter(
        method='filter_search_parcial',
        label='Busca Parcial',
        help_text='Busca parcial por número da OS ou número da ocorrência'
    )
    
    # ===== FILTROS DE STATUS =====
    status = django_filters.ChoiceFilter(
        choices=OrdemServico.Status.choices,
        label='Status'
    )
    
    # ===== FILTROS DE PERITO =====
    perito_id = django_filters.NumberFilter(
        field_name='ocorrencia__perito_atribuido__id',
        label='Perito Destinatário'
    )
    
    # ===== FILTROS DE DATA =====
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
    
    # ===== FILTROS BOOLEANOS =====
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
    
    # ===== FILTROS PERSONALIZADOS =====
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
            'numero_ocorrencia_exato',
            'numero_os_exato',
            'search'
        ]

    # ===== MÉTODOS DE FILTRO =====
    
    def filter_search_parcial(self, queryset, name, value):
        """Busca parcial por número da OS ou ocorrência"""
        if not value:
            return queryset
        return queryset.filter(
            Q(numero_os__icontains=value) |
            Q(ocorrencia__numero_ocorrencia__icontains=value)
        )

    def _get_queryset_com_vencimento(self, queryset):
        """
        Helper: Adiciona campo calculado de data de vencimento
        Reutilizado por filter_vencida e filter_urgencia
        """
        return queryset.annotate(
            data_vencimento_calculada=ExpressionWrapper(
                F('data_ciencia') + (F('prazo_dias') * timedelta(days=1)),
                output_field=DateTimeField()
            )
        )

    def filter_vencida(self, queryset, name, value):
        """
        ✅ OTIMIZADO: Filtra OS vencidas usando cálculo no banco
        """
        if value is None:
            return queryset

        queryset_anotado = self._get_queryset_com_vencimento(queryset)
        agora = timezone.now()

        if value:
            # Retorna apenas vencidas (prazo expirado e não concluída)
            return queryset_anotado.filter(
                data_vencimento_calculada__lt=agora,
                status__in=[
                    OrdemServico.Status.ABERTA,
                    OrdemServico.Status.EM_ANDAMENTO,
                    OrdemServico.Status.VENCIDA
                ]
            )
        else:
            # Retorna não vencidas
            return queryset.filter(
                Q(data_ciencia__isnull=True) |  # Sem ciência = não começou
                Q(status=OrdemServico.Status.CONCLUIDA) |  # Concluída
                Q(id__in=queryset_anotado.filter(
                    data_vencimento_calculada__gte=agora
                ).values_list('id', flat=True))  # Prazo ainda não expirou
            )

    def filter_urgencia(self, queryset, name, value):
        """
        ✅ CORRIGIDO: Implementa filtro de urgência baseado em dias restantes
        """
        if not value:
            return queryset

        # OS concluídas
        if value == 'concluida':
            return queryset.filter(status=OrdemServico.Status.CONCLUIDA)

        # Para os outros casos, precisa calcular dias restantes
        queryset_anotado = self._get_queryset_com_vencimento(queryset)
        agora = timezone.now()

        # Filtra apenas não concluídas com data de ciência
        queryset_ativas = queryset_anotado.filter(
            data_ciencia__isnull=False
        ).exclude(
            status=OrdemServico.Status.CONCLUIDA
        )

        if value == 'vermelho':
            # Vencida (prazo já passou)
            return queryset_ativas.filter(data_vencimento_calculada__lt=agora)
        
        elif value == 'laranja':
            # 1-2 dias restantes
            limite_inferior = agora
            limite_superior = agora + timedelta(days=2)
            return queryset_ativas.filter(
                data_vencimento_calculada__gte=limite_inferior,
                data_vencimento_calculada__lt=limite_superior
            )
        
        elif value == 'amarelo':
            # 3-4 dias restantes
            limite_inferior = agora + timedelta(days=2)
            limite_superior = agora + timedelta(days=4)
            return queryset_ativas.filter(
                data_vencimento_calculada__gte=limite_inferior,
                data_vencimento_calculada__lt=limite_superior
            )
        
        elif value == 'verde':
            # 5+ dias restantes
            limite = agora + timedelta(days=4)
            return queryset_ativas.filter(data_vencimento_calculada__gte=limite)

        return queryset

    def filter_sem_ciencia(self, queryset, name, value):
        """Filtra OS sem ciência do perito"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(ciente_por__isnull=True)
        else:
            return queryset.filter(ciente_por__isnull=False)

    def filter_com_justificativa(self, queryset, name, value):
        """Filtra OS com justificativa de atraso"""
        if value is None:
            return queryset
        if value:
            return queryset.exclude(justificativa_atraso__exact='')
        else:
            return queryset.filter(justificativa_atraso__exact='')

    def filter_apenas_originais(self, queryset, name, value):
        """Filtra apenas OS originais (não reiterações)"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(numero_reiteracao=0)
        return queryset
    
    def filter_apenas_reiteracoes(self, queryset, name, value):
        """Filtra apenas reiterações"""
        if value is None:
            return queryset
        if value:
            return queryset.filter(numero_reiteracao__gt=0)
        return queryset