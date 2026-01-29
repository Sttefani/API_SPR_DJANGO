from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

# IMPORTAÇÃO ADICIONADA PARA A ORDENAÇÃO CORRETA
from django.db.models.functions import Length
from .models import Exame
from .serializers import ExameSerializer, ExameLixeiraSerializer
from .permissions import ExamePermission


class ExameViewSet(viewsets.ModelViewSet):
    # AJUSTE: Agora o queryset base já vem ordenado de forma "inteligente"
    queryset = (
        Exame.objects.select_related("parent", "servico_pericial")
        .annotate(codigo_len=Length("codigo"))
        .order_by("codigo_len", "codigo")
    )

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

        # Para as demais ações, usa o queryset ordenado numericamente definido acima
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == "lixeira":
            return ExameLixeiraSerializer
        return ExameSerializer

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
            .order_by("-deleted_at")
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
