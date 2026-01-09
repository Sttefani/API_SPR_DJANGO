# cidades/views.py

from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Cidade, Bairro
from .serializers import (
    CidadeSerializer,
    CidadeLixeiraSerializer,
    BairroSerializer,
    BairroDropdownSerializer,
    BairroLixeiraSerializer,
)
from .permissions import CidadePermission


class CidadeViewSet(viewsets.ModelViewSet):
    queryset = Cidade.objects.all().order_by("nome")
    permission_classes = [CidadePermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ["nome"]

    def get_queryset(self):
        """Sobrescreve queryset para actions específicas"""
        if self.action in ["restaurar", "lixeira"]:
            return Cidade.all_objects.all()
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == "lixeira":
            return CidadeLixeiraSerializer
        return CidadeSerializer

    @action(detail=False, methods=["get"], pagination_class=None)
    def dropdown(self, request):
        queryset = self.get_queryset().order_by("nome")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
        lixeira_qs = Cidade.all_objects.filter(deleted_at__isnull=False).order_by(
            "-deleted_at"
        )
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response(
                {"detail": "Esta cidade não está deletada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class BairroViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciamento de Bairros.
    Suporta filtro por cidade via query param: ?cidade_id=1
    """

    queryset = Bairro.objects.all().order_by("cidade__nome", "nome")
    permission_classes = [CidadePermission]  # Mesma permissão de Cidade
    filter_backends = [filters.SearchFilter]
    search_fields = ["nome", "cidade__nome"]

    def get_queryset(self):
        """Filtra por cidade se o parâmetro for passado"""
        queryset = super().get_queryset()

        if self.action in ["restaurar", "lixeira"]:
            return Bairro.all_objects.all()

        # Filtro por cidade (usado no dropdown do frontend)
        cidade_id = self.request.query_params.get("cidade_id")
        if cidade_id:
            queryset = queryset.filter(cidade_id=cidade_id)

        return queryset

    def get_serializer_class(self):
        if self.action == "lixeira":
            return BairroLixeiraSerializer
        if self.action == "dropdown":
            return BairroDropdownSerializer
        return BairroSerializer

    @action(detail=False, methods=["get"], pagination_class=None)
    def dropdown(self, request):
        """
        Retorna lista de bairros para dropdown.
        Uso: GET /api/bairros/dropdown/?cidade_id=1
        """
        cidade_id = request.query_params.get("cidade_id")

        if not cidade_id:
            return Response(
                {"detail": "O parâmetro 'cidade_id' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = Bairro.objects.filter(cidade_id=cidade_id).order_by("nome")
        serializer = BairroDropdownSerializer(queryset, many=True)
        return Response(serializer.data)

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
        lixeira_qs = Bairro.all_objects.filter(deleted_at__isnull=False).order_by(
            "-deleted_at"
        )
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response(
                {"detail": "Este bairro não está deletado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
