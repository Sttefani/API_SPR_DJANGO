from rest_framework import viewsets, status, filters, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import IntegrityError
from django.db.models import Q
import re
from .models import ProcedimentoCadastrado
from .serializers import ProcedimentoCadastradoSerializer, ProcedimentoCadastradoLixeiraSerializer
from .permissions import ProcedimentoCadastradoPermission

class ProcedimentoCadastradoViewSet(viewsets.ModelViewSet):
    queryset = ProcedimentoCadastrado.objects.select_related('tipo_procedimento').all().order_by('-ano', '-numero')
    permission_classes = [ProcedimentoCadastradoPermission]
    filter_backends = []
    search_fields = ['numero', 'ano', 'tipo_procedimento__sigla', 'tipo_procedimento__nome']

    def get_queryset(self):
        if self.action in ['restaurar', 'lixeira']:
            return ProcedimentoCadastrado.all_objects.select_related('tipo_procedimento').all()

        queryset = super().get_queryset()
        search_term = self.request.query_params.get('search', None)

        if not search_term:
            return queryset

        pattern = re.compile(r'([A-Z\s-]+)\s*-\s*(\w+)\s*/\s*(\d{4})', re.IGNORECASE)
        match = pattern.match(search_term.strip())

        if match:
            sigla, numero, ano = match.groups()
            return queryset.filter(
                tipo_procedimento__sigla__iexact=sigla.strip(),
                numero__iexact=numero.strip(),
                ano=ano
            )
        else:
            try:
                ano_busca = int(search_term)
                ano_filter = Q(ano=ano_busca)
            except ValueError:
                ano_filter = Q()

            return queryset.filter(
                Q(numero__icontains=search_term) |
                Q(tipo_procedimento__sigla__icontains=search_term) |
                Q(tipo_procedimento__nome__icontains=search_term) |
                ano_filter
            ).distinct()

    def get_serializer_class(self):
        if self.action == 'lixeira':
            return ProcedimentoCadastradoLixeiraSerializer
        return ProcedimentoCadastradoSerializer

    def perform_create(self, serializer):
        try:
            serializer.save(created_by=self.request.user)
        except IntegrityError:
            tipo = serializer.validated_data.get('tipo_procedimento')
            numero = serializer.validated_data.get('numero', '').upper()
            ano = serializer.validated_data.get('ano')
            raise serializers.ValidationError({
                'numero': f'Já existe um procedimento {tipo.sigla} nº {numero}/{ano} cadastrado no sistema.'
            })

    def perform_update(self, serializer):
        try:
            serializer.save(updated_by=self.request.user)
        except IntegrityError:
            tipo = serializer.validated_data.get('tipo_procedimento')
            numero = serializer.validated_data.get('numero', '').upper()
            ano = serializer.validated_data.get('ano')
            raise serializers.ValidationError({
                'numero': f'Já existe um procedimento {tipo.sigla} nº {numero}/{ano} cadastrado no sistema.'
            })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def lixeira(self, request):
        lixeira_qs = ProcedimentoCadastrado.all_objects.select_related('tipo_procedimento').filter(deleted_at__isnull=False).order_by('-deleted_at')
        serializer = self.get_serializer(lixeira_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'detail': 'Este procedimento não está deletado.'}, status=status.HTTP_400_BAD_REQUEST)
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def verificar_existente(self, request):
        tipo_procedimento_id = request.GET.get('tipo_procedimento_id')
        numero = request.GET.get('numero', '').upper()
        ano = request.GET.get('ano')
        
        if not all([tipo_procedimento_id, numero, ano]):
            return Response({'exists': False})
        
        procedimento = ProcedimentoCadastrado.objects.filter(
            tipo_procedimento_id=tipo_procedimento_id,
            numero=numero,
            ano=ano
        ).first()
        
        if procedimento:
            serializer = self.get_serializer(procedimento)
            return Response({
                'exists': True,
                'procedimento': serializer.data
            })
        
        return Response({'exists': False})
    
    @action(detail=True, methods=['get'])
    def ocorrencias_vinculadas(self, request, pk=None):
        procedimento = self.get_object()
        ocorrencias = procedimento.ocorrencias.all().order_by('-created_at')
        
        from ocorrencias.serializers import OcorrenciaListSerializer
        serializer = OcorrenciaListSerializer(ocorrencias, many=True)
        
        return Response({
            'procedimento': {
                'id': procedimento.id,
                'tipo': procedimento.tipo_procedimento.sigla,
                'numero': procedimento.numero,
                'ano': procedimento.ano
            },
            'total_ocorrencias': ocorrencias.count(),
            'ocorrencias': serializer.data
        })