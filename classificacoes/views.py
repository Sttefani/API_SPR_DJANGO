from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from .models import ClassificacaoOcorrencia
from .serializers import (
    ClassificacaoOcorrenciaSerializer,
    ClassificacaoOcorrenciaLixeiraSerializer,
)
from .permissions import ClassificacaoPermission


class ClassificacaoOcorrenciaViewSet(viewsets.ModelViewSet):
    # Base: Traz o pai junto para otimizar e ordena por código (essencial para árvores)
    queryset = ClassificacaoOcorrencia.objects.select_related("parent").order_by(
        "codigo"
    )
    serializer_class = ClassificacaoOcorrenciaSerializer
    permission_classes = [ClassificacaoPermission]

    # Desativei o SearchFilter automático para usarmos nossa lógica manual robusta
    filter_backends = []

    pagination_class = None

    def get_queryset(self):
        # 1. Lógica especial para lixeira (traz tudo, inclusive deletados)
        if self.action in ["restaurar", "lixeira"]:
            return ClassificacaoOcorrencia.all_objects.select_related(
                "parent"
            ).order_by("-deleted_at")

        queryset = super().get_queryset()

        # 2. Captura parâmetros
        search = self.request.query_params.get("search", "").strip()
        parent_id = self.request.query_params.get("parent_id")
        raiz = self.request.query_params.get("raiz")

        # 3. LÓGICA DE BUSCA MANUAL (A SOLUÇÃO DO SEU PROBLEMA)
        if search:
            # Procura o termo no Nome/Código do item OU no Nome/Código do PAI do item
            queryset = queryset.filter(
                Q(nome__icontains=search)
                | Q(codigo__icontains=search)
                | Q(
                    parent__nome__icontains=search
                )  # <--- Traz os filhos se o nome do pai bater
                | Q(
                    parent__codigo__icontains=search
                )  # <--- Traz os filhos se o código do pai bater
            ).distinct()  # Evita duplicatas

            # Quando tem busca, retornamos tudo o que achou, ignorando filtro de raiz
            return queryset

        # 4. Filtros de navegação (só aplicam se NÃO tiver busca)
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)

        elif raiz == "true":
            # Se pediu raiz e não tá buscando nem filtrando ID, manda só os pais
            queryset = queryset.filter(parent__isnull=True)

        return queryset

    def get_serializer_class(self):
        if self.action == "lixeira":
            return ClassificacaoOcorrenciaLixeiraSerializer
        return ClassificacaoOcorrenciaSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def lixeira(self, request):
        lixeira_qs = (
            ClassificacaoOcorrencia.all_objects.select_related("parent")
            .filter(deleted_at__isnull=False)
            .order_by("-deleted_at")
        )
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response(
                {"detail": "Esta classificação não está deletada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], pagination_class=None)
    def dropdown(self, request):
        """
        Retorna lista filtrada por serviço para uso em combobox
        """
        queryset = ClassificacaoOcorrencia.objects.all().order_by("codigo")
        servico_id = request.query_params.get("servico_id")

        if servico_id:
            try:
                servico_id = int(servico_id)

                # 1. Pais associados ao serviço
                grupos_pais_ids = ClassificacaoOcorrencia.objects.filter(
                    parent__isnull=True, servicos_periciais__id=servico_id
                ).values_list("id", flat=True)

                # 2. Filhos desses pais OU filhos orfãos associados
                queryset = queryset.filter(
                    Q(subgrupos__isnull=True)
                    & (
                        Q(parent_id__in=grupos_pais_ids)
                        | Q(servicos_periciais__id=servico_id)
                    )
                ).distinct()

            except (ValueError, TypeError):
                return Response(status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
