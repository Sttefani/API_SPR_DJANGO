import django_filters
from .models import ProtocoloEntrega


class ProtocoloEntregaFilter(django_filters.FilterSet):
    status_recebimento = django_filters.ChoiceFilter(
        choices=ProtocoloEntrega.StatusRecebimento.choices
    )
    tipo_entrega = django_filters.ChoiceFilter(
        choices=ProtocoloEntrega.TipoEntrega.choices
    )
    vestigio = django_filters.NumberFilter(field_name='vestigio__id')
    ocorrencia = django_filters.NumberFilter(field_name='ocorrencia__id')
    unidade_demandante = django_filters.NumberFilter(field_name='unidade_demandante__id')
    entregue_por = django_filters.NumberFilter(field_name='entregue_por__id')
    data_de  = django_filters.DateFilter(field_name='entregue_em', lookup_expr='date__gte')
    data_ate = django_filters.DateFilter(field_name='entregue_em', lookup_expr='date__lte')

    class Meta:
        model = ProtocoloEntrega
        fields = [
            'status_recebimento', 'tipo_entrega',
            'vestigio', 'ocorrencia', 'unidade_demandante', 'entregue_por',
            'data_de', 'data_ate',
        ]
