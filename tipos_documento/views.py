# tipos_documento/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import TipoDocumento
from .serializers import TipoDocumentoSerializer, TipoDocumentoLixeiraSerializer
from .permissions import TipoDocumentoPermission


class TipoDocumentoViewSet(viewsets.ModelViewSet):
    queryset = TipoDocumento.all_objects.all()
    permission_classes = [TipoDocumentoPermission]
    filterset_fields = ['nome']

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return TipoDocumentoLixeiraSerializer
        return TipoDocumentoSerializer

    def list(self, request, *args, **kwargs):
        queryset = TipoDocumento.objects.all()
        queryset = self.filter_queryset(queryset)
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

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        lixeira_qs = TipoDocumento.all_objects.filter(deleted_at__isnull=False)
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


from django.shortcuts import render

# Create your views here.
