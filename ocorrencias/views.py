# ocorrencias/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from servicos_periciais.models import ServicoPericial

from .models import Ocorrencia
from .serializers import (
    OcorrenciaCreateSerializer,
    OcorrenciaListSerializer, 
    OcorrenciaDetailSerializer,
    OcorrenciaUpdateSerializer,
    OcorrenciaLixeiraSerializer, 
    FinalizarComAssinaturaSerializer,
    ReabrirOcorrenciaSerializer
)
from .permissions import (
    OcorrenciaPermission, 
    PodeEditarOcorrencia, 
    PodeFinalizarOcorrencia, 
    PodeReabrirOcorrencia,
    PeritoAtribuidoRequired
)
from .filters import OcorrenciaFilter
from .pdf_generator import (
    gerar_pdf_ocorrencia,
    gerar_pdf_ocorrencias_por_perito,
    gerar_pdf_ocorrencias_por_ano,
    gerar_pdf_ocorrencias_por_status,
    gerar_pdf_ocorrencias_por_servico,
    gerar_pdf_ocorrencias_por_cidade,
    gerar_pdf_relatorio_geral
)


class OcorrenciaViewSet(viewsets.ModelViewSet):
    queryset = Ocorrencia.all_objects.select_related(
        'servico_pericial',
        'unidade_demandante',
        'autoridade__cargo',
        'cidade',
        'classificacao',
        'procedimento_cadastrado__tipo_procedimento',
        'tipo_documento_origem',
        'perito_atribuido',
        'created_by',
        'updated_by',
        'finalizada_por',
        'reaberta_por',
        'ficha_local_crime',
        'ficha_acidente_transito',
        'ficha_constatacao_substancia',
        'ficha_documentoscopia',
        'ficha_material_diverso'
    ).prefetch_related(
        'exames_solicitados'
    ).all()
    permission_classes = [OcorrenciaPermission]
    filterset_class = OcorrenciaFilter
    search_fields = ['numero_ocorrencia', 'perito_atribuido__nome_completo', 'autoridade__nome']
    
    def get_permissions(self):
        if self.action in ['adicionar_exames', 'remover_exames']:
            return [PeritoAtribuidoRequired()]
        if self.action == 'finalizar':
            return [PodeFinalizarOcorrencia()]
        if self.action == 'reabrir':
            return [PodeReabrirOcorrencia()]
        if self.action in ['update', 'partial_update']:
            return [PodeEditarOcorrencia()]
        return [permission() for permission in self.permission_classes]
    
    def get_serializer_class(self):
        if self.action in ['list', 'finalizadas', 'pendentes']:
            return OcorrenciaListSerializer
        if self.action == 'lixeira':
            return OcorrenciaLixeiraSerializer
        if self.action == 'finalizar':
            return FinalizarComAssinaturaSerializer
        if self.action == 'reabrir':
            return ReabrirOcorrenciaSerializer
        if self.action in ['update', 'partial_update']:
            return OcorrenciaUpdateSerializer
        if self.action == 'create':
            return OcorrenciaCreateSerializer
        return OcorrenciaDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        if user.is_superuser or user.perfil == 'ADMINISTRATIVO':
            if self.action != 'lixeira':
                queryset = queryset.filter(deleted_at__isnull=True)
            return queryset
        
        return queryset.filter(
            servico_pericial__in=user.servicos_periciais.all(),
            deleted_at__isnull=True
        )

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
        queryset = self.get_queryset().filter(deleted_at__isnull=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
        
    @action(detail=True, methods=['get'])
    def imprimir(self, request, pk=None):
        ocorrencia = self.get_object()
        pdf_response = gerar_pdf_ocorrencia(ocorrencia, request)
        return pdf_response
            
    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        instance = self.get_object()
        instance.restore()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get', 'post'])
    def finalizar(self, request, pk=None):
        ocorrencia = self.get_object()
        
        if request.method == 'POST':
            from ordens_servico.models import OrdemServico
            ordens_pendentes = ocorrencia.ordens_servico.exclude(
                status=OrdemServico.Status.CONCLUIDA
            ).filter(deleted_at__isnull=True)
            
            if ordens_pendentes.exists():
                numeros_os = list(ordens_pendentes.values_list('numero_os', flat=True))
                return Response(
                    {"error": f"Não é possível finalizar a ocorrência. As Ordens de Serviço a seguir ainda estão pendentes: {numeros_os}. Por favor, conclua ou cancele estas OS primeiro."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if ocorrencia.esta_finalizada:
                return Response({'error': 'Esta ocorrência já foi finalizada.'}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
            ocorrencia.finalizar_com_assinatura(request.user, ip_address)
            
            response_serializer = OcorrenciaDetailSerializer(ocorrencia, context={'request': request})
            return Response({'message': 'Ocorrência finalizada com sucesso.', 'ocorrencia': response_serializer.data}, status=status.HTTP_200_OK)
        
        serializer = self.get_serializer(instance=ocorrencia)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'])
    def reabrir(self, request, pk=None):
        ocorrencia = self.get_object()
        if request.method == 'POST':
            if not ocorrencia.esta_finalizada:
                return Response({'error': 'Esta ocorrência não está finalizada.'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
                motivo = serializer.validated_data.get('motivo_reabertura')
                ocorrencia.reabrir(request.user, motivo, ip_address)
                response_serializer = OcorrenciaDetailSerializer(ocorrencia, context={'request': request})
                return Response({'message': 'Ocorrência reaberta com sucesso.', 'ocorrencia': response_serializer.data}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance=ocorrencia)
        return Response(serializer.data)
        
    @action(detail=True, methods=['patch'])
    def atribuir_perito(self, request, pk=None):
        ocorrencia = self.get_object()
        if ocorrencia.esta_finalizada:
            return Response({'error': 'Não é possível atribuir perito a uma ocorrência finalizada.'}, status=status.HTTP_400_BAD_REQUEST)
        perito_id = request.data.get('perito_id')
        if not perito_id:
            return Response({'error': 'perito_id é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from usuarios.models import User
            perito = User.objects.get(id=perito_id, perfil='PERITO')
            if ocorrencia.perito_atribuido and not request.user.is_superuser:
                return Response({'error': 'Apenas super administradores podem alterar o perito já atribuído.'}, status=status.HTTP_403_FORBIDDEN)
            ocorrencia.perito_atribuido = perito
            ocorrencia.updated_by = request.user
            ocorrencia.save()
            serializer = self.get_serializer(ocorrencia)
            return Response({'message': f'Perito {perito.nome_completo} atribuído com sucesso.', 'ocorrencia': serializer.data})
        except User.DoesNotExist:
            return Response({'error': 'Perito não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def finalizadas(self, request):
        queryset = self.get_queryset().filter(status='FINALIZADA', finalizada_por__isnull=False).order_by('-data_assinatura_finalizacao')
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'results': serializer.data})
    
    @action(detail=False, methods=['get'])
    def pendentes(self, request):
        queryset = self.get_queryset().exclude(status='FINALIZADA').order_by('-created_at')
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'results': serializer.data})
    
    @action(detail=True, methods=['get'])
    def historico_assinatura(self, request, pk=None):
        ocorrencia = self.get_object()
        if not ocorrencia.esta_finalizada:
            return Response({'error': 'Esta ocorrência não foi finalizada ainda.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'numero_ocorrencia': ocorrencia.numero_ocorrencia,
            'assinatura_digital': { 
                'finalizada_por': {
                    'id': ocorrencia.finalizada_por.id, 
                    'nome': ocorrencia.finalizada_por.nome_completo, 
                    'perfil': ocorrencia.finalizada_por.perfil
                }, 
                'data_assinatura': ocorrencia.data_assinatura_finalizacao, 
                'ip_origem': ocorrencia.ip_assinatura_finalizacao 
            },
        })

    @action(detail=True, methods=['post'])
    def adicionar_exames(self, request, pk=None):
        ocorrencia = self.get_object()
        
        if ocorrencia.esta_finalizada:
            return Response(
                {"error": "Não é possível alterar exames de uma ocorrência finalizada."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        if ocorrencia.perito_atribuido:
            if not user.is_superuser and user.id != ocorrencia.perito_atribuido.id:
                return Response(
                    {"error": "Apenas o perito atribuído pode alterar os exames desta ocorrência."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        exames_ids = request.data.get('exames_ids', [])
        if not isinstance(exames_ids, list):
            return Response({"error": "O campo 'exames_ids' deve ser uma lista de IDs."}, status=status.HTTP_400_BAD_REQUEST)
        
        if exames_ids:
            from exames.models import Exame
            existing_ids = list(Exame.objects.filter(id__in=exames_ids).values_list('id', flat=True))
            invalid_ids = set(exames_ids) - set(existing_ids)
            if invalid_ids:
                return Response(
                    {"error": f"Exames inválidos: {list(invalid_ids)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        ocorrencia.exames_solicitados.add(*exames_ids)
        serializer = OcorrenciaDetailSerializer(ocorrencia, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def remover_exames(self, request, pk=None):
        ocorrencia = self.get_object()
        
        if ocorrencia.esta_finalizada:
            return Response(
                {"error": "Não é possível alterar exames de uma ocorrência finalizada."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        if ocorrencia.perito_atribuido:
            if not user.is_superuser and user.id != ocorrencia.perito_atribuido.id:
                return Response(
                    {"error": "Apenas o perito atribuído pode alterar os exames desta ocorrência."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        exames_ids = request.data.get('exames_ids', [])
        if not isinstance(exames_ids, list):
            return Response({"error": "O campo 'exames_ids' deve ser uma lista de IDs."}, status=status.HTTP_400_BAD_REQUEST)
        
        if exames_ids:
            exames_atuais = list(ocorrencia.exames_solicitados.values_list('id', flat=True))
            ids_nao_vinculados = set(exames_ids) - set(exames_atuais)
            if ids_nao_vinculados:
                return Response(
                    {"error": f"Exames não vinculados à ocorrência: {list(ids_nao_vinculados)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        ocorrencia.exames_solicitados.remove(*exames_ids)
        serializer = OcorrenciaDetailSerializer(ocorrencia, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def definir_exames(self, request, pk=None):
        ocorrencia = self.get_object()
        
        if ocorrencia.esta_finalizada:
            return Response(
                {"error": "Não é possível alterar exames de uma ocorrência finalizada."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        if ocorrencia.perito_atribuido:
            if not user.is_superuser and user.id != ocorrencia.perito_atribuido.id:
                return Response(
                    {"error": "Apenas o perito atribuído pode alterar os exames desta ocorrência."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        exames_ids = request.data.get('exames_ids', [])
        
        if not isinstance(exames_ids, list):
            return Response(
                {"error": "O campo 'exames_ids' deve ser uma lista de IDs."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if exames_ids:
            from exames.models import Exame
            existing_ids = list(Exame.objects.filter(id__in=exames_ids).values_list('id', flat=True))
            invalid_ids = set(exames_ids) - set(existing_ids)
            if invalid_ids:
                return Response(
                    {"error": f"Exames inválidos: {list(invalid_ids)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        ocorrencia.exames_solicitados.set(exames_ids)
        
        serializer = OcorrenciaDetailSerializer(ocorrencia, context={'request': request})
        return Response({
            'message': f'{len(exames_ids)} exames definidos para a ocorrência.',
            'ocorrencia': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def exames_disponiveis(self, request):
        from exames.models import Exame
        
        search = request.GET.get('search', '')
        servico_pericial_id = request.GET.get('servico_pericial_id', '')
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        
        queryset = Exame.objects.all().order_by('codigo')
        
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) | Q(codigo__icontains=search)
            )
        
        if servico_pericial_id:
            queryset = queryset.filter(servico_pericial_id=servico_pericial_id)
        
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        exames = queryset[start:end]
        
        from exames.serializers import ExameNestedSerializer
        serializer = ExameNestedSerializer(exames, many=True)
        
        return Response({
            'exames': serializer.data,
            'pagination': {
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size,
                'has_next': end < total,
                'has_previous': page > 1
            }
        })

    @action(detail=True, methods=['get'])
    def exames_atuais(self, request, pk=None):
        ocorrencia = self.get_object()
        
        from exames.serializers import ExameNestedSerializer
        serializer = ExameNestedSerializer(
            ocorrencia.exames_solicitados.all().order_by('codigo'), 
            many=True
        )
        
        return Response({
            'ocorrencia_id': ocorrencia.id,
            'numero_ocorrencia': ocorrencia.numero_ocorrencia,
            'exames_atuais': serializer.data,
            'total_exames': ocorrencia.exames_solicitados.count()
        })

    @action(detail=False, methods=['get'], url_path='relatorio-perito/(?P<perito_id>[^/.]+)')
    def relatorio_por_perito(self, request, perito_id=None, *args, **kwargs):
        try:
            perito_id = int(perito_id)
        except ValueError:
            return Response(
                {"error": "ID do perito deve ser um número válido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return gerar_pdf_ocorrencias_por_perito(perito_id, request)

    @action(detail=False, methods=['get'], url_path='relatorio-ano/(?P<ano>[^/.]+)')
    def relatorio_por_ano(self, request, ano=None, *args, **kwargs):
        try:
            ano = int(ano)
            if ano < 2000 or ano > 2050:
                raise ValueError("Ano inválido")
        except ValueError:
            return Response(
                {"error": "Ano deve ser um número válido entre 2000 e 2050."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return gerar_pdf_ocorrencias_por_ano(ano, request)

    @action(detail=False, methods=['get'], url_path='relatorio-status/(?P<status_param>[^/.]+)')
    def relatorio_por_status(self, request, status_param=None, *args, **kwargs):
        status_validos = [choice[0] for choice in Ocorrencia.Status.choices]
        if status_param not in status_validos:
            return Response(
                {"error": f"Status inválido. Opções: {', '.join(status_validos)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return gerar_pdf_ocorrencias_por_status(status_param, request)

    @action(detail=False, methods=['get'], url_path='relatorio-servico/(?P<servico_id>[^/.]+)')
    def relatorio_por_servico(self, request, servico_id=None, *args, **kwargs):
        try:
            servico_id = int(servico_id)
        except ValueError:
            return Response(
                {"error": "ID do serviço deve ser um número válido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return gerar_pdf_ocorrencias_por_servico(servico_id, request)

    @action(detail=False, methods=['get'], url_path='relatorio-cidade/(?P<cidade_id>[^/.]+)')
    def relatorio_por_cidade(self, request, cidade_id=None, *args, **kwargs):
        try:
            cidade_id = int(cidade_id)
        except ValueError:
            return Response(
                {"error": "ID da cidade deve ser um número válido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return gerar_pdf_ocorrencias_por_cidade(cidade_id, request)

    @action(detail=False, methods=['get'], url_path='relatorio-geral')
    def relatorio_geral(self, request, *args, **kwargs):
        return gerar_pdf_relatorio_geral(request)
    
    
    @action(detail=False, methods=['get'])
    def estatisticas(self, request):
        user = request.user
        hoje = timezone.now().date()
        inicio_mes = hoje.replace(day=1)
        servico_id = request.GET.get('servico_id', None)
        
        # Tratar valores inválidos como None
        if servico_id in ['null', '', 'undefined']:
            servico_id = None
        
        if user.perfil == 'PERITO':
            minhas = Ocorrencia.objects.filter(
                perito_atribuido=user, 
                deleted_at__isnull=True
            )
            
            if servico_id:
                minhas = minhas.filter(servico_pericial_id=servico_id)
                servicos_ids = [int(servico_id)]
            else:
                servicos_ids = list(user.servicos_periciais.values_list('id', flat=True))
            
            do_servico = Ocorrencia.objects.filter(
                servico_pericial_id__in=servicos_ids,
                deleted_at__isnull=True
            )
            
            data_limite = hoje - timedelta(days=20)
            atrasadas = minhas.filter(
                status__in=['AGUARDANDO_PERITO', 'EM_ANALISE'],
                created_at__date__lt=data_limite
            )
            
            finalizadas_mes = minhas.filter(
                status='FINALIZADA',
                data_finalizacao__gte=inicio_mes
            )
            
            ultimas = minhas.order_by('-created_at')[:5].values(
                'id', 'numero_ocorrencia', 'status', 'created_at'
            )
            
            total_minhas = minhas.count()
            total_finalizadas = minhas.filter(status='FINALIZADA').count()
            taxa_finalizacao = (total_finalizadas / total_minhas * 100) if total_minhas > 0 else 0
            
            total_servico = do_servico.count()
            participacao = (total_minhas / total_servico * 100) if total_servico > 0 else 0
            
            meus_servicos = ServicoPericial.objects.filter(
                id__in=servicos_ids,
                deleted_at__isnull=True
            )
            
            por_servico = []
            for servico in meus_servicos:
                total = minhas.filter(servico_pericial=servico).count()
                por_servico.append({
                    'servico_pericial__sigla': servico.sigla,
                    'servico_pericial__nome': servico.nome,
                    'total': total
                })
            
            por_servico = sorted(por_servico, key=lambda x: x['total'], reverse=True)
            
            return Response({
                'minhas_ocorrencias': {
                    'total': total_minhas,
                    'aguardando': minhas.filter(status='AGUARDANDO_PERITO').count(),
                    'em_analise': minhas.filter(status='EM_ANALISE').count(),
                    'finalizadas': total_finalizadas,
                    'atrasadas': atrasadas.count(),
                    'finalizadas_este_mes': finalizadas_mes.count(),
                    'taxa_finalizacao': round(taxa_finalizacao, 1),
                },
                'servico': {
                    'total_geral': total_servico,
                    'minha_participacao': round(participacao, 1),
                },
                'ultimas_ocorrencias': list(ultimas),
                'por_servico': por_servico
            })
        
        elif user.perfil == 'OPERACIONAL':
            servicos_ids = list(user.servicos_periciais.values_list('id', flat=True))
            
            if servico_id:
                servicos_ids = [int(servico_id)] if int(servico_id) in servicos_ids else servicos_ids
            
            todas = Ocorrencia.objects.filter(
                servico_pericial_id__in=servicos_ids,
                deleted_at__isnull=True
            )
            
            data_limite = hoje - timedelta(days=20)
            atrasadas = todas.filter(
                status__in=['AGUARDANDO_PERITO', 'EM_ANALISE'],
                created_at__date__lt=data_limite
            )
            
            finalizadas_mes = todas.filter(
                status='FINALIZADA',
                data_finalizacao__gte=inicio_mes
            )
            
            meus_servicos = ServicoPericial.objects.filter(
                id__in=servicos_ids,
                deleted_at__isnull=True
            )
            
            por_servico = []
            for servico in meus_servicos:
                total = todas.filter(servico_pericial=servico).count()
                por_servico.append({
                    'servico_pericial__sigla': servico.sigla,
                    'servico_pericial__nome': servico.nome,
                    'total': total
                })
            
            por_servico = sorted(por_servico, key=lambda x: x['total'], reverse=True)
            
            dias_30 = hoje - timedelta(days=30)
            criadas_30dias = todas.filter(created_at__date__gte=dias_30).count()
            finalizadas_30dias = todas.filter(
                status='FINALIZADA',
                data_finalizacao__gte=dias_30
            ).count()
            
            return Response({
                'geral': {
                    'total': todas.count(),
                    'aguardando': todas.filter(status='AGUARDANDO_PERITO').count(),
                    'em_analise': todas.filter(status='EM_ANALISE').count(),
                    'finalizadas': todas.filter(status='FINALIZADA').count(),
                    'sem_perito': todas.filter(perito_atribuido__isnull=True).count(),
                    'atrasadas': atrasadas.count(),
                    'finalizadas_este_mes': finalizadas_mes.count(),
                },
                'ultimos_30_dias': {
                    'criadas': criadas_30dias,
                    'finalizadas': finalizadas_30dias,
                },
                'por_servico': por_servico
            })
        
        elif user.perfil == 'ADMINISTRATIVO' or user.is_superuser:
            todas = Ocorrencia.objects.filter(deleted_at__isnull=True)
            
            if servico_id:
                todas = todas.filter(servico_pericial_id=servico_id)
            
            data_limite = hoje - timedelta(days=20)
            atrasadas = todas.filter(
                status__in=['AGUARDANDO_PERITO', 'EM_ANALISE'],
                created_at__date__lt=data_limite
            )
            
            finalizadas_mes = todas.filter(
                status='FINALIZADA',
                data_finalizacao__gte=inicio_mes
            )
            
            if servico_id:
                todos_servicos = ServicoPericial.objects.filter(
                    id=servico_id,
                    deleted_at__isnull=True
                )
            else:
                todos_servicos = ServicoPericial.objects.filter(deleted_at__isnull=True)
            
            por_servico = []
            for servico in todos_servicos:
                total = todas.filter(servico_pericial=servico).count()
                por_servico.append({
                    'servico_pericial__sigla': servico.sigla,
                    'servico_pericial__nome': servico.nome,
                    'total': total
                })
            
            por_servico = sorted(por_servico, key=lambda x: x['total'], reverse=True)
            
            dias_30 = hoje - timedelta(days=30)
            criadas_30dias = todas.filter(created_at__date__gte=dias_30).count()
            finalizadas_30dias = todas.filter(
                status='FINALIZADA',
                data_finalizacao__gte=dias_30
            ).count()
            
            return Response({
                'geral': {
                    'total': todas.count(),
                    'aguardando': todas.filter(status='AGUARDANDO_PERITO').count(),
                    'em_analise': todas.filter(status='EM_ANALISE').count(),
                    'finalizadas': todas.filter(status='FINALIZADA').count(),
                    'sem_perito': todas.filter(perito_atribuido__isnull=True).count(),
                    'atrasadas': atrasadas.count(),
                    'finalizadas_este_mes': finalizadas_mes.count(),
                },
                'ultimos_30_dias': {
                    'criadas': criadas_30dias,
                    'finalizadas': finalizadas_30dias,
                },
                'por_servico': por_servico
            })
        
        return Response({'detail': 'Perfil não reconhecido'}, status=400)
    
    # Em OcorrenciaViewSet
    @action(detail=True, methods=['post'])
    def vincular_procedimento(self, request, pk=None):
        """Vincula um procedimento a uma ocorrência que não possui procedimento"""
        ocorrencia = self.get_object()
        
        # Validação: Já tem procedimento?
        if ocorrencia.procedimento_cadastrado:
            if not request.user.is_superuser:
                return Response({
                    'error': f'Esta ocorrência já está vinculada ao procedimento {ocorrencia.procedimento_cadastrado}. Apenas super administradores podem alterar.'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Validação: Ocorrência finalizada?
        if ocorrencia.esta_finalizada:
            return Response({
                'error': 'Não é possível vincular procedimento a uma ocorrência finalizada.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        procedimento_id = request.data.get('procedimento_cadastrado_id')
        
        if not procedimento_id:
            return Response({
                'error': 'procedimento_cadastrado_id é obrigatório.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from procedimentos_cadastrados.models import ProcedimentoCadastrado
            procedimento = ProcedimentoCadastrado.objects.get(id=procedimento_id)
            
            # Log da vinculação (importante para auditoria)
            old_procedimento = ocorrencia.procedimento_cadastrado
            ocorrencia.procedimento_cadastrado = procedimento
            ocorrencia.updated_by = request.user
            ocorrencia.save()
            
            # Opcional: criar log específico
            # HistoricoVinculacao.objects.create(
            #     ocorrencia=ocorrencia,
            #     procedimento_antigo=old_procedimento,
            #     procedimento_novo=procedimento,
            #     usuario=request.user
            # )
            
            serializer = self.get_serializer(ocorrencia)
            return Response({
                'message': f'Procedimento {procedimento} vinculado com sucesso.',
                'ocorrencia': serializer.data
            })
            
        except ProcedimentoCadastrado.DoesNotExist:
            return Response({
                'error': 'Procedimento não encontrado.'
            }, status=status.HTTP_404_NOT_FOUND)