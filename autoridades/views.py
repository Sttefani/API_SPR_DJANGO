from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .models import Autoridade
from .serializers import AutoridadeSerializer, AutoridadeLixeiraSerializer
from .permissions import AutoridadePermission


class AutoridadeViewSet(viewsets.ModelViewSet):
    queryset = Autoridade.objects.select_related("cargo").all().order_by("nome")
    serializer_class = AutoridadeSerializer
    permission_classes = [AutoridadePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["cargo"]
    search_fields = ["nome", "cargo__nome"]

    def get_queryset(self):
        if self.action in ["restaurar", "lixeira"]:
            return Autoridade.all_objects.select_related("cargo").all()
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == "lixeira":
            return AutoridadeLixeiraSerializer
        return AutoridadeSerializer

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
            Autoridade.all_objects.select_related("cargo")
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
                {"detail": "Esta autoridade não está deletada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
