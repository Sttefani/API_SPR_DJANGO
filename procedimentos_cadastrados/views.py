# procedimentos_cadastrados/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
import datetime
from .models import ProcedimentoCadastrado
from .serializers import ProcedimentoCadastradoSerializer, ProcedimentoCadastradoLixeiraSerializer
from .permissions import ProcedimentoCadastradoPermission


class ProcedimentoCadastradoViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para gerenciar Procedimentos Cadastrados.
    """
    # O queryset principal agora aponta para todos os objetos (ativos e deletados)
    # para que as actions de 'retrieve' e 'restore' funcionem corretamente.
    queryset = ProcedimentoCadastrado.all_objects.select_related('tipo_procedimento').all()

    permission_classes = [ProcedimentoCadastradoPermission]
    filterset_fields = ['tipo_procedimento__sigla', 'numero', 'ano']

    def get_serializer_class(self):
        """
        Retorna o serializer apropriado dependendo da ação.
        """
        if self.action == 'lixeira':
            return ProcedimentoCadastradoLixeiraSerializer
        return ProcedimentoCadastradoSerializer

    def get_serializer_context(self):
        """
        Garante que o ano atual seja passado como valor inicial para o formulário
        da interface de teste do DRF (Browsable API).
        """
        context = super().get_serializer_context()
        if self.action == 'create':
            context['view'].initial = {'ano': datetime.date.today().year}
        return context

    def list(self, request, *args, **kwargs):
        """
        Sobrescreve a ação 'list' para mostrar apenas os procedimentos ATIVOS.
        """
        queryset = ProcedimentoCadastrado.objects.select_related('tipo_procedimento').all()
        queryset = self.filter_queryset(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
        Salva o 'created_by' automaticamente.
        """
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """
        Salva o 'updated_by' automaticamente.
        """
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        Executa o soft delete.
        """
        instance = self.get_object()
        instance.soft_delete(user=self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        """
        Mostra os procedimentos que estão na lixeira.
        """
        lixeira_qs = ProcedimentoCadastrado.all_objects.filter(deleted_at__isnull=False)
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        """
        Restaura um procedimento da lixeira.
        """
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)