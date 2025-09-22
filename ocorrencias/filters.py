# ocorrencias/filters.py
import django_filters
from django import forms
from django.db.models import Q
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
        if value is True:
            return queryset.filter(exames_solicitados__isnull=False).distinct()
        elif value is False:
            return queryset.filter(exames_solicitados__isnull=True)
        return queryset

    def filter_prazo_status(self, queryset, name, value):
        from django.utils import timezone
        from django.db.models import Case, When, IntegerField
        
        hoje = timezone.now().date()
        
        if value == 'CONCLUIDO':
            return queryset.filter(data_finalizacao__isnull=False)
        elif value == 'NO_PRAZO':
            return queryset.filter(
                data_finalizacao__isnull=True
            ).extra(
                where=["DATE(%s) - DATE(created_at) <= 10"],
                params=[hoje]
            )
        elif value == 'PRORROGADO':
            return queryset.filter(
                data_finalizacao__isnull=True
            ).extra(
                where=["DATE(%s) - DATE(created_at) BETWEEN 11 AND 20"],
                params=[hoje]
            )
        elif value == 'ATRASADO':
            return queryset.filter(
                data_finalizacao__isnull=True
            ).extra(
                where=["DATE(%s) - DATE(created_at) > 20"],
                params=[hoje]
            )
        return queryset

    def filter_busca_geral(self, queryset, name, value):
        """Busca em múltiplos campos simultaneamente"""
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