# ordens_servico/filters.py

import django_filters
from django.db.models import Q, F # Removido ExpressionWrapper, DateTimeField
from django.utils import timezone
from datetime import timedelta # Mantido para filter_urgencia
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
    # ✅ NOTA: A choice 'VENCIDA' não existe mais no models.py,
    #    então o Django Filter não a incluirá automaticamente aqui. Correto.
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
        method='filter_sem_ciencia', # Método correto já existia
        label='Sem Ciência'
    )

    com_justificativa = django_filters.BooleanFilter(
        method='filter_com_justificativa', # Método correto já existia
        label='Com Justificativa de Atraso'
    )

    # ===== FILTROS PERSONALIZADOS =====
    urgencia = django_filters.ChoiceFilter(
        method='filter_urgencia',
        choices=[
            ('verde', 'Verde (5+ dias)'),
            ('amarelo', 'Amarelo (3-4 dias)'),
            ('laranja', 'Laranja (1-2 dias)'),
            ('vermelho', 'Vermelho (Vencida/Hoje)'), # Label ajustado
            ('concluida', 'Concluída'),
            #('sem_ciencia', 'Sem Ciência'), # Se quiser filtrar por sem ciência aqui também
        ],
        label='Urgência'
    )

    apenas_originais = django_filters.BooleanFilter(
        field_name='numero_reiteracao', # Simplificado: Usa field_name direto
        lookup_expr='exact',
        label='Apenas OS Originais',
        method='filter_boolean_numero_reiteracao_0' # Método para tratar True/False
    )

    apenas_reiteracoes = django_filters.BooleanFilter(
        field_name='numero_reiteracao', # Simplificado: Usa field_name direto
        lookup_expr='gt',
        label='Apenas Reiterações',
        method='filter_boolean_numero_reiteracao_gt_0' # Método para tratar True/False
    )

    class Meta:
        model = OrdemServico
        # Lista de campos simplificada, muitos são cobertos pelos filtros definidos acima
        fields = [
            'status',
            'perito_id',
            'data_inicio',
            'data_fim',
            # Os filtros booleanos e customizados não precisam estar aqui
            # se já foram definidos explicitamente acima com 'method' ou 'field_name'.
            'numero_ocorrencia_exato',
            'numero_os_exato',
            'search',
            'unidade_demandante', # Adicionado filtro por unidade (se existir no frontend)
            'ocorrencia__servico_pericial', # Adicionado filtro por serviço (se existir no frontend)
        ]

    # ===== MÉTODOS DE FILTRO =====

    def filter_search_parcial(self, queryset, name, value):
        """Busca parcial por número da OS ou ocorrência"""
        if not value:
            return queryset
        # Garante que a busca por ocorrência use o campo correto
        return queryset.filter(
            Q(numero_os__icontains=value) |
            Q(ocorrencia__numero_ocorrencia__icontains=value)
        )

    # ❌ MÉTODO OBSOLETO REMOVIDO (Não precisamos mais calcular a data)
    # def _get_queryset_com_vencimento(self, queryset): ...

    def filter_vencida(self, queryset, name, value):
        """
        ✅ CORRIGIDO: Filtra OS vencidas usando o campo data_prazo.
        """
        if value is None:
            return queryset

        hoje = timezone.now().date()

        # Filtra OS que NÃO estão concluídas E cuja data_prazo já passou
        q_vencidas = Q(data_prazo__lt=hoje) & ~Q(status=OrdemServico.Status.CONCLUIDA)

        if value: # Se ?vencida=true, retorna apenas as vencidas
            return queryset.filter(q_vencidas)
        else: # Se ?vencida=false, retorna as NÃO vencidas
            # Não vencida = (Está concluída OU (Não tem data_prazo OU data_prazo >= hoje))
             return queryset.exclude(q_vencidas)
            # Alternativa explícita para 'else':
            # return queryset.filter(
            #     Q(status=OrdemServico.Status.CONCLUIDA) |
            #     Q(data_prazo__isnull=True) |
            #     Q(data_prazo__gte=hoje)
            # )


    def filter_urgencia(self, queryset, name, value):
        """
        ✅ CORRIGIDO: Implementa filtro de urgência baseado em dias restantes usando data_prazo.
        """
        if not value:
            return queryset

        hoje = timezone.now().date()

        # OS concluídas
        if value == 'concluida':
            return queryset.filter(status=OrdemServico.Status.CONCLUIDA)

        # Filtra apenas OS ativas (não concluídas e com data_prazo definida)
        queryset_ativas = queryset.filter(
            data_prazo__isnull=False
        ).exclude(
            status=OrdemServico.Status.CONCLUIDA
        )

        if value == 'vermelho':
            # Vencida ou Vence Hoje (data_prazo <= hoje)
            return queryset_ativas.filter(data_prazo__lte=hoje)

        elif value == 'laranja':
            # 1-2 dias restantes (data_prazo é amanhã ou depois de amanhã)
            amanha = hoje + timedelta(days=1)
            depois_de_amanha = hoje + timedelta(days=2)
            return queryset_ativas.filter(
                data_prazo__gte=amanha,
                data_prazo__lte=depois_de_amanha
            )

        elif value == 'amarelo':
            # 3-4 dias restantes
            dia_mais_3 = hoje + timedelta(days=3)
            dia_mais_4 = hoje + timedelta(days=4)
            return queryset_ativas.filter(
                data_prazo__gte=dia_mais_3,
                data_prazo__lte=dia_mais_4
            )

        elif value == 'verde':
            # 5+ dias restantes (data_prazo >= hoje + 5 dias)
            limite_verde = hoje + timedelta(days=5)
            return queryset_ativas.filter(data_prazo__gte=limite_verde)

        # Se value for 'sem_ciencia' (opcional)
        # elif value == 'sem_ciencia':
        #    return queryset.filter(data_prazo__isnull=True, status=OrdemServico.Status.AGUARDANDO_CIENCIA)


        return queryset # Retorna queryset original se o valor não corresponder

    def filter_sem_ciencia(self, queryset, name, value):
        """Filtra OS sem ciência do perito"""
        if value is None:
            return queryset
        # Sem ciência = status AGUARDANDO_CIENCIA e ciente_por é nulo
        q_sem_ciencia = Q(status=OrdemServico.Status.AGUARDANDO_CIENCIA) & Q(ciente_por__isnull=True)
        if value:
            return queryset.filter(q_sem_ciencia)
        else:
            return queryset.exclude(q_sem_ciencia)

    def filter_com_justificativa(self, queryset, name, value):
        """Filtra OS com justificativa de atraso preenchida"""
        if value is None:
            return queryset
        # Com justificativa = campo não é nulo e não é string vazia
        q_com_justificativa = Q(justificativa_atraso__isnull=False) & ~Q(justificativa_atraso__exact='')
        if value:
            return queryset.filter(q_com_justificativa)
        else:
            return queryset.exclude(q_com_justificativa)

    # Métodos helpers para filtros booleanos baseados em numero_reiteracao
    def filter_boolean_numero_reiteracao_0(self, queryset, name, value):
        if value is True:
            return queryset.filter(numero_reiteracao=0)
        elif value is False:
             return queryset.exclude(numero_reiteracao=0)
        return queryset # Retorna sem filtro se value não for True/False

    def filter_boolean_numero_reiteracao_gt_0(self, queryset, name, value):
        if value is True:
            return queryset.filter(numero_reiteracao__gt=0)
        elif value is False:
             return queryset.exclude(numero_reiteracao__gt=0)
        return queryset