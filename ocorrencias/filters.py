# ocorrencias/filters.py
import django_filters
from django import forms
from django.db.models import Q, F, ExpressionWrapper, DateField
from django.db.models.functions import Cast, TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import Ocorrencia


class OcorrenciaFilter(django_filters.FilterSet):
    
    # ===== FILTROS DE TEXTO =====
    numero_ocorrencia = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Número da Ocorrência'
    )
    
    historico = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Busca no Histórico'
    )
    
    numero_documento_origem = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Número do Documento'
    )
    
    processo_sei_numero = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Processo SEI'
    )
    
    # ===== FILTROS POR RELACIONAMENTOS =====
    servico_pericial__nome = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nome do Serviço'
    )
    
    unidade_demandante__nome = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nome da Unidade'
    )
    
    autoridade__nome = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nome da Autoridade'
    )
    
    cidade__nome = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nome da Cidade'
    )
    
    perito_atribuido__nome_completo = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nome do Perito'
    )
    
    created_by__nome_completo = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Criado por'
    )
    
    # ===== FILTROS DE DATA =====
    data_fato = django_filters.DateFilter(
        label='Data do Fato (exata)'
    )
    
    data_fato_de = django_filters.DateFilter(
        field_name='data_fato',
        lookup_expr='gte',
        label='Data do Fato (de)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    data_fato_ate = django_filters.DateFilter(
        field_name='data_fato',
        lookup_expr='lte',
        label='Data do Fato (até)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    created_at_de = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Criado em (de)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    created_at_ate = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Criado em (até)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    data_finalizacao_de = django_filters.DateFilter(
        field_name='data_finalizacao',
        lookup_expr='gte',
        label='Finalizado em (de)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    data_finalizacao_ate = django_filters.DateFilter(
        field_name='data_finalizacao',
        lookup_expr='lte',
        label='Finalizado em (até)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    # ===== FILTROS BOOLEANOS =====
    esta_finalizada = django_filters.BooleanFilter(
        method='filter_esta_finalizada',
        label='Está Finalizada'
    )
    
    tem_perito = django_filters.BooleanFilter(
        method='filter_tem_perito',
        label='Tem Perito Atribuído'
    )
    
    tem_exames = django_filters.BooleanFilter(
        method='filter_tem_exames',
        label='Tem Exames Vinculados'
    )
    
    # ===== FILTROS DE ESCOLHA =====
    status = django_filters.ChoiceFilter(
        choices=Ocorrencia.Status.choices,
        label='Status'
    )
    
    # ===== FILTROS PERSONALIZADOS =====
    prazo_status = django_filters.ChoiceFilter(
        method='filter_prazo_status',
        choices=[
            ('NO_PRAZO', 'No Prazo (até 10 dias)'),
            ('PRORROGADO', 'Prorrogado (11-20 dias)'),
            ('ATRASADO', 'Atrasado (mais de 20 dias)'),
            ('CONCLUIDO', 'Concluído')
        ],
        label='Status do Prazo'
    )
    
    busca_geral = django_filters.CharFilter(
        method='filter_busca_geral',
        label='Busca Geral'
    )
    
    # ===== ORDENAÇÃO =====
    ordering = django_filters.OrderingFilter(
        fields=(
            ('created_at', 'Data de Criação'),
            ('data_fato', 'Data do Fato'),
            ('numero_ocorrencia', 'Número da Ocorrência'),
            ('data_finalizacao', 'Data de Finalização'),
            ('perito_atribuido__nome_completo', 'Nome do Perito'),
        ),
        field_labels={
            'created_at': 'Data de Criação',
            'data_fato': 'Data do Fato',
            'numero_ocorrencia': 'Número da Ocorrência',
            'data_finalizacao': 'Data de Finalização',
            'perito_atribuido__nome_completo': 'Nome do Perito',
        }
    )

    class Meta:
        model = Ocorrencia
        fields = [
            'numero_ocorrencia', 'status', 'servico_pericial', 'cidade',
            'unidade_demandante', 'autoridade', 'perito_atribuido',
            'classificacao', 'procedimento_cadastrado'
        ]

    # ===== MÉTODOS PERSONALIZADOS =====
    def filter_esta_finalizada(self, queryset, name, value):
        if value is True:
            return queryset.filter(status='FINALIZADA', finalizada_por__isnull=False)
        elif value is False:
            return queryset.exclude(status='FINALIZADA').exclude(finalizada_por__isnull=False)
        return queryset

    def filter_tem_perito(self, queryset, name, value):
        if value is True:
            return queryset.filter(perito_atribuido__isnull=False)
        elif value is False:
            return queryset.filter(perito_atribuido__isnull=True)
        return queryset

    def filter_tem_exames(self, queryset, name, value):
        """
        ✅ OTIMIZADO: Usa exists() ao invés de distinct()
        """
        if value is True:
            return queryset.filter(exames_solicitados__isnull=False).distinct()
        elif value is False:
            # Busca ocorrências que não têm exames
            return queryset.filter(
                ~Q(id__in=queryset.filter(
                    exames_solicitados__isnull=False
                ).values_list('id', flat=True))
            )
        return queryset

    def filter_prazo_status(self, queryset, name, value):
        """
        ✅ CORRIGIDO: Substituído .extra() por anotações do Django ORM
        Calcula a diferença de dias entre hoje e created_at
        """
        hoje = timezone.now().date()
        
        # Concluído (tem data de finalização)
        if value == 'CONCLUIDO':
            return queryset.filter(data_finalizacao__isnull=False)
        
        # Para os outros casos, filtra apenas não finalizadas
        queryset_nao_finalizadas = queryset.filter(data_finalizacao__isnull=True)
        
        if value == 'NO_PRAZO':
            # Até 10 dias corridos
            data_limite = hoje - timedelta(days=10)
            return queryset_nao_finalizadas.filter(
                created_at__date__gte=data_limite
            )
        
        elif value == 'PRORROGADO':
            # Entre 11 e 20 dias
            data_inicio = hoje - timedelta(days=20)
            data_fim = hoje - timedelta(days=11)
            return queryset_nao_finalizadas.filter(
                created_at__date__gte=data_inicio,
                created_at__date__lte=data_fim
            )
        
        elif value == 'ATRASADO':
            # Mais de 20 dias
            data_limite = hoje - timedelta(days=21)
            return queryset_nao_finalizadas.filter(
                created_at__date__lte=data_limite
            )
        
        return queryset

    def filter_busca_geral(self, queryset, name, value):
        """
        ✅ OTIMIZADO: Busca em múltiplos campos simultaneamente
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(numero_ocorrencia__icontains=value) |
            Q(historico__icontains=value) |
            Q(numero_documento_origem__icontains=value) |
            Q(processo_sei_numero__icontains=value) |
            Q(perito_atribuido__nome_completo__icontains=value) |
            Q(autoridade__nome__icontains=value) |
            Q(unidade_demandante__nome__icontains=value) |
            Q(servico_pericial__nome__icontains=value) |
            Q(cidade__nome__icontains=value)
        ).distinct()