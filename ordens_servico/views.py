# ordens_servico/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from .models import OrdemServico
from .serializers import (
    OrdemServicoSerializer,
    OrdemServicoLixeiraSerializer,
    CriarOrdemServicoComAssinaturaSerializer,
    TomarCienciaSerializer,
    ReiterarOrdemServicoSerializer,
    JustificarAtrasoSerializer
)
from .permissions import OrdemServicoPermission
from .filters import OrdemServicoFilter
from .pdf_generator import (
    gerar_pdf_ordem_servico,
    gerar_pdf_oficial_ordem_servico,
    gerar_pdf_listagem_ordens_servico
)
from ocorrencias.models import Ocorrencia


class OrdemServicoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar Ordens de Serviço (módulo independente).
    
    Endpoints principais:
    - GET/POST   /api/ordens-servico/
    - GET/PATCH/DELETE  /api/ordens-servico/{id}/
    
    Query params úteis:
    - ?ocorrencia_id=1  → Filtra OS de uma ocorrência específica
    - ?vencida=true     → Filtra apenas vencidas
    - ?sem_ciencia=true → Filtra sem ciência
    
    Actions customizadas:
    - POST  /api/ordens-servico/{id}/tomar-ciencia/
    - POST  /api/ordens-servico/{id}/reiterar/
    - POST  /api/ordens-servico/{id}/iniciar-trabalho/
    - POST  /api/ordens-servico/{id}/justificar-atraso/
    - POST  /api/ordens-servico/{id}/concluir/
    - GET   /api/ordens-servico/{id}/pdf/
    - GET   /api/ordens-servico/{id}/pdf-oficial/
    - GET   /api/ordens-servico/listagem-pdf/?ocorrencia_id=1
    - GET   /api/ordens-servico/lixeira/
    - POST  /api/ordens-servico/{id}/restaurar/
    """
    
    queryset = OrdemServico.all_objects.select_related(
        'ocorrencia',
        'ocorrencia__perito_atribuido',
        'ocorrencia__servico_pericial',
        'created_by',
        'updated_by',
        'ordenada_por',
        'ciente_por',
        'concluida_por',
        'unidade_demandante',
        'autoridade_demandante',
        'procedimento',
        'tipo_documento_referencia',
        'os_original'
    ).prefetch_related('reiteracoes').all()
    
    permission_classes = [OrdemServicoPermission]
    filterset_class = OrdemServicoFilter

    def get_queryset(self):
        """
        Filtra o queryset com base no usuário.
        Pode filtrar por ocorrência usando query param: ?ocorrencia_id=1
        """
        user = self.request.user
        queryset = self.queryset
        
        # Filtro opcional por ocorrência (via query param)
        ocorrencia_id = self.request.query_params.get('ocorrencia_id')
        if ocorrencia_id:
            queryset = queryset.filter(ocorrencia_id=ocorrencia_id)
        
        # Lixeira inclui deletados
        if self.action == 'lixeira':
            return queryset.filter(deleted_at__isnull=False)
        
        # Demais actions só mostram não-deletados
        queryset = queryset.filter(deleted_at__isnull=True)
        
        # Super Admin e Admin veem todas as OS
        if user.is_superuser or user.perfil == 'ADMINISTRATIVO':
            return queryset
        
        # Perito vê apenas as OS de ocorrências que lhe foram atribuídas
        return queryset.filter(ocorrencia__perito_atribuido=user)

    def get_serializer_class(self):
        """Retorna o serializer correto para cada ação"""
        if self.action == 'create':
            return CriarOrdemServicoComAssinaturaSerializer
        if self.action == 'tomar_ciencia':
            return TomarCienciaSerializer
        if self.action == 'reiterar':
            return ReiterarOrdemServicoSerializer
        if self.action == 'justificar_atraso':
            return JustificarAtrasoSerializer
        if self.action == 'lixeira':
            return OrdemServicoLixeiraSerializer
        
        return OrdemServicoSerializer
    
    def create(self, request, *args, **kwargs):
        """Cria uma nova Ordem de Serviço com assinatura digital"""
        ocorrencia_id = request.data.get('ocorrencia_id')
        
        if not ocorrencia_id:
            return Response(
                {"error": "Campo 'ocorrencia_id' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ocorrencia = Ocorrencia.objects.select_related(
                'perito_atribuido',
                'unidade_demandante',
                'autoridade',
                'procedimento_cadastrado'
            ).get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            return Response(
                {"error": "Ocorrência não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validações de negócio
        if ocorrencia.status == Ocorrencia.Status.FINALIZADA:
            return Response(
                {"error": "Não é possível emitir OS para ocorrência finalizada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not ocorrencia.perito_atribuido:
            return Response(
                {"error": "A ocorrência precisa ter um perito atribuído antes de emitir OS."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cria a OS com assinatura
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'ocorrencia': ocorrencia}
        )
        serializer.is_valid(raise_exception=True)
        ordem_servico = serializer.save()
        
        # Retorna com o serializer completo
        response_serializer = OrdemServicoSerializer(
            ordem_servico,
            context={'request': request}
        )
        
        return Response(
            {
                'message': f'Ordem de Serviço {ordem_servico.numero_os} emitida com sucesso.',
                'ordem_servico': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retorna detalhes de uma OS.
        Registra visualização automaticamente para o perito.
        """
        instance = self.get_object()
        
        # Registra visualização se for o perito destinatário
        if (instance.ocorrencia.perito_atribuido and
            request.user.id == instance.ocorrencia.perito_atribuido.id):
            instance.registrar_visualizacao()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        """Registra quem atualizou"""
        serializer.save(updated_by=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete - só Super Admin pode deletar"""
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(
            {'message': f'OS {instance.numero_os} movida para a lixeira.'},
            status=status.HTTP_204_NO_CONTENT
        )

    # =========================================================================
    # ACTIONS CUSTOMIZADAS
    # =========================================================================
    
    @action(detail=False, methods=['get'], url_path='pendentes-ciencia')
    def pendentes_ciencia(self, request):
        """
        Retorna a quantidade de OS aguardando ciência do perito logado
        """
        user = request.user
        
        print("=" * 80)
        print("🔍 DEBUG PENDENTES-CIENCIA")
        print("=" * 80)
        print(f"👤 Usuário logado: {user.username} (ID: {user.id})")
        print(f"📧 Email: {user.email}")
        print(f"👔 Nome: {user.nome_completo}")
        print(f"🎭 Perfil: {user.perfil}")
        print("-" * 80)
        
        # APENAS PERITOS veem o banner
        if user.perfil == 'ADMINISTRATIVO':
            print("❌ É ADMINISTRATIVO - retornando count=0")
            return Response({'count': 0, 'ordens': []})
        
        print("✅ É PERITO - buscando OS aguardando ciência...")
        print("-" * 80)
        
        # BUSCA TODAS as OS com status AGUARDANDO_CIENCIA (sem filtro de perito)
        todas_os_aguardando = OrdemServico.objects.filter(
            status='AGUARDANDO_CIENCIA',
            deleted_at__isnull=True
        ).select_related('ocorrencia', 'ocorrencia__perito_atribuido')
        
        print(f"📊 TOTAL de OS aguardando ciência no sistema: {todas_os_aguardando.count()}")
        print("-" * 80)
        
        if todas_os_aguardando.exists():
            print("📋 LISTA DE TODAS AS OS AGUARDANDO CIÊNCIA:")
            for os in todas_os_aguardando:
                perito = os.ocorrencia.perito_atribuido
                if perito:
                    print(f"   • OS {os.numero_os}")
                    print(f"     - Perito: {perito.nome_completo} (ID: {perito.id})")
                    print(f"     - Ocorrência: {os.ocorrencia.numero_ocorrencia}")
                    print(f"     - Status: {os.status}")
                    print(f"     - Deleted: {os.deleted_at}")
                else:
                    print(f"   • OS {os.numero_os} - SEM PERITO ATRIBUÍDO!")
            print("-" * 80)
        else:
            print("⚠️ NENHUMA OS com status AGUARDANDO_CIENCIA encontrada!")
            print("-" * 80)
        
        # Busca OS aguardando ciência DO PERITO LOGADO
        ordens = OrdemServico.objects.filter(
            status='AGUARDANDO_CIENCIA',
            ocorrencia__perito_atribuido=user,
            deleted_at__isnull=True
        ).select_related('ocorrencia').order_by('-created_at')
        
        print(f"🎯 OS ATRIBUÍDAS AO USUÁRIO LOGADO: {ordens.count()}")
        
        if ordens.exists():
            print("✅ ENCONTRADAS:")
            for os in ordens:
                print(f"   • {os.numero_os}")
        else:
            print("❌ NENHUMA OS encontrada para este perito!")
            print(f"   Verifique se o perito ID {user.id} está atribuído nas OS listadas acima")
        
        print("=" * 80)
        
        # Serializa dados mínimos
        dados = []
        for os in ordens:
            dados.append({
                'id': os.id,
                'numero_os': os.numero_os,
                'dias_desde_emissao': os.dias_desde_emissao,
                'created_at': os.created_at.isoformat()
            })
        
        return Response({
            'count': ordens.count(),
            'ordens': dados
        })
        
    @action(detail=True, methods=['post'], url_path='tomar-ciencia')
    def tomar_ciencia(self, request, pk=None, **kwargs):
        """Permite que o perito registre ciência da OS com assinatura digital"""
        ordem_servico = self.get_object()
        
        # Validações
        if request.user != ordem_servico.ocorrencia.perito_atribuido:
            return Response(
                {"error": "Apenas o perito atribuído pode tomar ciência desta OS."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if ordem_servico.ciente_por:
            return Response(
                {"message": "Ciência já registrada para esta OS."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valida senha
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Registra ciência
        ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
        ordem_servico.tomar_ciencia(user=request.user, ip_address=ip_address)
        
        # Retorna resposta
        response_serializer = OrdemServicoSerializer(
            ordem_servico,
            context={'request': request}
        )
        
        return Response(
            {
                'message': f'Ciência registrada com sucesso para OS {ordem_servico.numero_os}.',
                'ordem_servico': response_serializer.data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def reiterar(self, request, pk=None, **kwargs):
        """
        Cria uma OS de reiteração baseada na original/anterior.
        Só ADMINISTRATIVO pode reiterar.
        """
        os_anterior = self.get_object()
        
        # Valida assinatura
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Remove dados de assinatura
        validated_data = serializer.validated_data.copy()
        validated_data.pop('email')
        validated_data.pop('password')
        
        # Cria reiteração
        ordenada_por = validated_data.get('ordenada_por_id')
        nova_os = os_anterior.reiterar(
            prazo_dias=validated_data['prazo_dias'],
            ordenada_por=ordenada_por,
            user=request.user,
            observacoes=validated_data.get('observacoes_administrativo', '')
        )
        
        # Retorna resposta
        response_serializer = OrdemServicoSerializer(
            nova_os,
            context={'request': request}
        )
        
        return Response(
            {
                'message': f'Reiteração {nova_os.numero_os} criada com sucesso.',
                'ordem_servico': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], url_path='iniciar-trabalho')
    def iniciar_trabalho(self, request, pk=None, **kwargs):
        """Permite que o perito marque a OS como EM_ANDAMENTO"""
        ordem_servico = self.get_object()
        
        # Validações
        if request.user != ordem_servico.ocorrencia.perito_atribuido:
            return Response(
                {"error": "Apenas o perito atribuído pode iniciar o trabalho."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if ordem_servico.status != OrdemServico.Status.ABERTA:
            return Response(
                {"error": f"OS está com status '{ordem_servico.get_status_display()}'. Só pode iniciar trabalho em OS 'Aberta'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Inicia trabalho
        ordem_servico.iniciar_trabalho(user=request.user)
        
        # Retorna resposta
        serializer = self.get_serializer(ordem_servico)
        return Response(
            {
                'message': 'Trabalho iniciado com sucesso.',
                'ordem_servico': serializer.data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='justificar-atraso')
    def justificar_atraso(self, request, pk=None, **kwargs):
        """Permite que o perito justifique o atraso na entrega"""
        ordem_servico = self.get_object()
        
        # Validações
        if request.user != ordem_servico.ocorrencia.perito_atribuido:
            return Response(
                {"error": "Apenas o perito atribuído pode justificar atraso."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not ordem_servico.esta_vencida:
            return Response(
                {"error": "Esta OS não está vencida."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Salva justificativa
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        ordem_servico.justificar_atraso(
            justificativa=serializer.validated_data['justificativa'],
            user=request.user
        )
        
        # Retorna resposta
        response_serializer = OrdemServicoSerializer(
            ordem_servico,
            context={'request': request}
        )
        
        return Response(
            {
                'message': 'Justificativa registrada com sucesso.',
                'ordem_servico': response_serializer.data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='concluir')
    def concluir(self, request, pk=None, **kwargs):
        """
        Marca a OS como concluída (dá baixa).
        Apenas ADMINISTRATIVO pode concluir.
        
        Endpoint: POST /api/ordens-servico/{id}/concluir/
        
        Validações:
        - Apenas admin pode concluir
        - OS não pode estar já concluída
        - Perito deve ter tomado ciência
        
        Retorna:
        - 200 OK: OS concluída com sucesso
        - 403 FORBIDDEN: Usuário sem permissão
        - 400 BAD_REQUEST: Validação de negócio falhou
        """
        ordem_servico = self.get_object()
        
        # ✅ VALIDAÇÃO 1: Apenas administrativos
        if request.user.perfil not in ['ADMINISTRATIVO', 'SUPER_ADMIN']:
            return Response(
                {'error': 'Apenas administrativos podem concluir ordens de serviço.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ✅ VALIDAÇÃO 2: Não pode concluir OS já concluída
        if ordem_servico.status == OrdemServico.Status.CONCLUIDA:
            return Response(
                {'error': 'Esta ordem de serviço já está concluída.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ VALIDAÇÃO 3: Perito deve ter tomado ciência
        if ordem_servico.status == OrdemServico.Status.AGUARDANDO_CIENCIA:
            return Response(
                {'error': 'O perito ainda não tomou ciência desta OS. A conclusão só é possível após a ciência.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ VALIDAÇÃO 4: Verificar se tem ciência (dupla checagem)
        if not ordem_servico.ciente_por:
            return Response(
                {'error': 'Esta OS não possui registro de ciência. Solicite ao perito que tome ciência primeiro.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ CONCLUI A OS (o método concluir() no model agora salva o concluida_por)
        ordem_servico.concluir(user=request.user)
        
        # ✅ RETORNA SUCESSO COM STATUS 200
        serializer = self.get_serializer(ordem_servico)
        return Response(
            {
                'message': f'OS {ordem_servico.numero_os} concluída com sucesso!',
                'ordem_servico': serializer.data
            },
            status=status.HTTP_200_OK
        )

    # =========================================================================
    # LIXEIRA E RESTAURAÇÃO
    # =========================================================================

    @action(detail=False, methods=['get'])
    def lixeira(self, request, **kwargs):
        """Lista as OS deletadas (soft delete)"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, **kwargs):
        """Restaura uma OS da lixeira"""
        instance = self.get_object()
        
        if not instance.deleted_at:
            return Response(
                {'message': 'Esta OS não está deletada.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.restore()
        serializer = self.get_serializer(instance)
        
        return Response(
            {
                'message': f'OS {instance.numero_os} restaurada com sucesso.',
                'ordem_servico': serializer.data
            },
            status=status.HTTP_200_OK
        )

    # =========================================================================
    # GERAÇÃO DE PDFs
    # =========================================================================
    
    @action(detail=True, methods=['get'], url_path='pdf')
    def gerar_pdf(self, request, pk=None):
        """Gera PDF simples da OS"""
        ordem = self.get_object()
        
        # ✅ CORRIGIDO: Administrativos veem tudo sempre
        if request.user.perfil in ['ADMINISTRATIVO', 'SUPER_ADMIN']:
            return gerar_pdf_ordem_servico(ordem, request)
        
        # Peritos precisam tomar ciência primeiro
        if ordem.ocultar_detalhes_ate_ciencia():
            return Response(
                {'error': 'Você precisa tomar ciência da OS antes de gerar o PDF.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return gerar_pdf_ordem_servico(ordem, request)

    @action(detail=True, methods=['get'], url_path='pdf-oficial')
    def gerar_pdf_oficial(self, request, *args, **kwargs):
        """Gera PDF oficial da OS para impressão/assinatura"""
        ordem_servico = self.get_object()
        
        # ✅ CORRIGIDO: Administrativos veem tudo sempre
        if request.user.perfil in ['ADMINISTRATIVO', 'SUPER_ADMIN']:
            return gerar_pdf_oficial_ordem_servico(ordem_servico, request)
        
        # Peritos precisam tomar ciência primeiro
        if ordem_servico.ocultar_detalhes_ate_ciencia():
            return Response(
                {'error': 'Você precisa tomar ciência da OS antes de gerar o PDF oficial.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return gerar_pdf_oficial_ordem_servico(ordem_servico, request)

    @action(detail=False, methods=['get'], url_path='listagem-pdf')
    def gerar_listagem_pdf(self, request, *args, **kwargs):
        """Gera PDF com todas as OS de uma ocorrência"""
        ocorrencia_id = request.query_params.get('ocorrencia_id')
        
        if not ocorrencia_id:
            return Response(
                {"error": "Query param 'ocorrencia_id' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ocorrencia = Ocorrencia.objects.get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            return Response(
                {"error": "Ocorrência não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return gerar_pdf_listagem_ordens_servico(ocorrencia, request)