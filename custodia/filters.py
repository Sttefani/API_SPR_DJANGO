# custodia/filters.py

import django_filters
from .models import Vestigio, VestigioMovimentacao, DNA


class VestigioFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(lookup_expr='exact')
    servico_pericial = django_filters.NumberFilter(field_name='servico_pericial__id')
    unidade_demandante = django_filters.NumberFilter(field_name='unidade_demandante__id')
    
    # 💎 ADICIONADO: Permite que o Angular filtre vestígios por perito responsável
    user_destino = django_filters.NumberFilter(field_name='user_destino__id')
    
    biologico = django_filters.BooleanFilter()
    conformidade = django_filters.BooleanFilter()
    saiu_da_custodia = django_filters.BooleanFilter()
    ano_ocorrencia = django_filters.NumberFilter()
    lacre = django_filters.CharFilter(lookup_expr='icontains')
    num_processo_sei = django_filters.CharFilter(lookup_expr='icontains')
    ocorrencia = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Vestigio
        fields = [
            'status', 'servico_pericial', 'unidade_demandante', 'user_destino', # 💎 INCLUÍDO AQUI
            'biologico', 'conformidade', 'saiu_da_custodia',
            'ano_ocorrencia', 'lacre', 'num_processo_sei', 'ocorrencia',
        ]


class DNAFilter(django_filters.FilterSet):
    # Filtros espelhados do SPR-Custódia Java (DnaCustomRepository)
    nome              = django_filters.CharFilter(lookup_expr='icontains')
    cpf               = django_filters.CharFilter(lookup_expr='icontains')
    lacres            = django_filters.CharFilter(lookup_expr='icontains')
    uf                = django_filters.CharFilter(lookup_expr='exact')
    perito            = django_filters.NumberFilter(field_name='perito__id')
    situacao          = django_filters.CharFilter(lookup_expr='exact')
    finalidade_coleta = django_filters.CharFilter(lookup_expr='exact')
    vestigio          = django_filters.NumberFilter(field_name='vestigio__id')
    registrado_por_usuario_externo = django_filters.BooleanFilter()
    data_de          = django_filters.DateFilter(field_name='data_da_coleta', lookup_expr='gte')
    data_ate         = django_filters.DateFilter(field_name='data_da_coleta', lookup_expr='lte')

    class Meta:
        model = DNA
        fields = [
            'nome', 'cpf', 'lacres', 'uf', 'perito',
            'situacao', 'finalidade_coleta', 'vestigio',
            'registrado_por_usuario_externo', 'data_de', 'data_ate',
        ]