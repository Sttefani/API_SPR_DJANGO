# exames/views.py

from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from .models import Exame
from .serializers import ExameSerializer, ExameLixeiraSerializer
from .permissions import ExamePermission


class ExameViewSet(viewsets.ModelViewSet):
    # AJUSTE: Queryset base limpo. A ordenação pesada será feita no método 'list'.
    queryset = Exame.objects.select_related("parent", "servico_pericial").all()

    serializer_class = ExameSerializer
    permission_classes = [ExamePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["servico_pericial", "parent"]
    search_fields = ["codigo", "nome"]
    pagination_class = None

    def get_queryset(self):
        # Para a lixeira e restauração, mantemos a lógica de trazer todos (incluindo deletados)
        if self.action in ["restaurar", "lixeira"]:
            return Exame.all_objects.select_related("parent", "servico_pericial").all()

        # Para as demais ações, usa o queryset padrão definido acima
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == "lixeira":
            return ExameLixeiraSerializer
        return ExameSerializer

    # --- NOVO MÉTODO DE LISTAGEM COM ORDENAÇÃO INTELIGENTE (PYTHON) ---
    def list(self, request, *args, **kwargs):
        # 1. Pega os dados do banco já aplicando os filtros (pesquisa, serviço, etc.)
        queryset = self.filter_queryset(self.get_queryset())

        # 2. Ordena os resultados em memória usando Python.
        # Essa lógica separa ex: "10.1.2" em [10, 1, 2] e compara matematicamente.
        exames_ordenados = sorted(
            queryset,
            key=lambda x: [
                int(p) if p.isdigit() else p for p in (x.codigo or "").split(".")
            ],
        )

        # 3. Passa a lista perfeitamente ordenada para o Serializer
        serializer = self.get_serializer(exames_ordenados, many=True)
        return Response(serializer.data)

    # -------------------------------------------------------------------

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
            Exame.all_objects.select_related("parent", "servico_pericial")
            .filter(deleted_at__isnull=False)
            .order_by(
                "-deleted_at"
            )  # Na lixeira, faz sentido ordenar pelos mais recentes deletados
        )
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response(
                {"detail": "Este exame não está deletado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
