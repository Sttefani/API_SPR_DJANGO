# ordens_servico/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Count, Q, Avg, F, ExpressionWrapper, fields
from django.db.models.functions import TruncDate
from datetime import timedelta

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
                {
                    "error": "Não é possível emitir Ordem de Serviço para esta ocorrência.",
                    "details": "A ocorrência está com status 'Finalizada'. Ordens de Serviço só podem ser emitidas para ocorrências com status 'Aberta', 'Em Andamento' ou 'Aguardando Perícia'.",
                    "action": "Se necessário, altere o status da ocorrência antes de emitir a OS."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not ocorrencia.perito_atribuido:
            return Response(
                {
                    "error": "Não é possível emitir Ordem de Serviço.",
                    "details": "A ocorrência precisa ter um perito atribuído antes de emitir a OS.",
                    "action": "Vá em 'Editar Ocorrência', atribua um perito no campo 'Perito Atribuído' e tente novamente."
                },
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
            data_ciencia = ordem_servico.data_ciencia.strftime('%d/%m/%Y às %H:%M') if ordem_servico.data_ciencia else 'data desconhecida'
            return Response(
                {
                    "error": "Ciência já registrada para esta Ordem de Serviço.",
                    "details": f"Você já registrou ciência em {data_ciencia}. Não é necessário tomar ciência novamente.",
                    "context": {
                        "data_ciencia": data_ciencia,
                        "status_atual": ordem_servico.get_status_display()
                    }
                },
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
                'message': f'Ciência registrada com sucesso para OS {
                    ordem_servico.numero_os}.',
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
        from django.core.exceptions import ValidationError
        
        os_anterior = self.get_object()
        
        # Valida assinatura
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Remove dados de assinatura
        validated_data = serializer.validated_data.copy()
        validated_data.pop('email')
        validated_data.pop('password')
        
        # ✅ CORREÇÃO: Captura ValidationError para retornar mensagem amigável
        try:
            # Cria reiteração
            ordenada_por = validated_data.get('ordenada_por_id')
            nova_os = os_anterior.reiterar(
                prazo_dias=validated_data['prazo_dias'],
                ordenada_por=ordenada_por,
                user=request.user,
                observacoes=validated_data.get('observacoes_administrativo', '')
            )
        except ValidationError as e:
            # Retorna erro 400 com a mensagem do ValidationError
            error_message = e.messages[0] if hasattr(e, 'messages') else str(e)
            return Response(
                {'error': error_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Retorna resposta de sucesso
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
            status_atual = ordem_servico.get_status_display()
            
            # Mensagens específicas por status
            if ordem_servico.status == OrdemServico.Status.AGUARDANDO_CIENCIA:
                detalhes = "Você precisa tomar ciência da Ordem de Serviço antes de iniciar o trabalho."
                acao = "Clique em 'Tomar Ciência' primeiro, depois você poderá iniciar o trabalho."
            elif ordem_servico.status == OrdemServico.Status.EM_ANDAMENTO:
                detalhes = "Esta ordem já está com o trabalho iniciado."
                acao = "Não é necessário iniciar novamente. Continue trabalhando na OS."
            elif ordem_servico.status == OrdemServico.Status.CONCLUIDA:
                detalhes = "Esta ordem já foi concluída."
                acao = "Não é possível iniciar trabalho em uma OS já concluída."
            else:
                detalhes = f"O status atual é '{status_atual}'. Você só pode iniciar trabalho em ordens com status 'Aberta'."
                acao = "Verifique o status da ordem e o fluxo correto."
            
            return Response(
                {
                    "error": "Não é possível iniciar o trabalho nesta Ordem de Serviço.",
                    "details": detalhes,
                    "action": acao,
                    "context": {
                        "status_atual": status_atual,
                        "status_esperado": "Aberta"
                    }
                },
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
            # Melhora a mensagem com contexto de datas
            prazo_str = ordem_servico.data_prazo.strftime('%d/%m/%Y') if ordem_servico.data_prazo else 'Não definido'
            hoje_str = timezone.now().strftime('%d/%m/%Y')
            
            return Response(
                {
                    "error": "Esta Ordem de Serviço não está vencida.",
                    "details": "Você só pode justificar atraso em ordens que já passaram do prazo de entrega.",
                    "context": {
                        "prazo": prazo_str,
                        "hoje": hoje_str,
                        "status": ordem_servico.get_status_display()
                    }
                },
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
            perito_nome = ordem_servico.ocorrencia.perito_atribuido.nome_completo if ordem_servico.ocorrencia.perito_atribuido else 'o perito'
            return Response(
                {
                    'error': 'Não é possível concluir esta Ordem de Serviço.',
                    'details': f'{perito_nome} ainda não tomou ciência da ordem.',
                    'action': 'Aguarde o perito tomar ciência ou entre em contato com ele antes de dar baixa na OS.',
                    'context': {
                        'os_numero': ordem_servico.numero_os,
                        'status_atual': 'Aguardando Ciência'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ VALIDAÇÃO 4: Verificar se tem ciência (dupla checagem)
        if not ordem_servico.ciente_por:
            perito_nome = ordem_servico.ocorrencia.perito_atribuido.nome_completo if ordem_servico.ocorrencia.perito_atribuido else 'o perito'
            return Response(
                {
                    'error': 'Esta Ordem de Serviço não possui registro de ciência.',
                    'details': f'O sistema não identificou que {perito_nome} tomou ciência desta ordem.',
                    'action': f'Entre em contato com {perito_nome} para que ele tome ciência antes de você dar baixa.',
                    'context': {
                        'os_numero': ordem_servico.numero_os,
                        'perito': perito_nome
                    }
                },
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
    
    @action(detail=False, methods=['get'], url_path='relatorios-gerenciais')
    def relatorios_gerenciais(self, request):
        """
        Retorna relatórios gerenciais agregados sobre Ordens de Serviço.
        """
        
        # Preparar filtros base
        filtros = Q(deleted_at__isnull=True)
        
        # Filtro de data
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        
        if data_inicio:
            filtros &= Q(created_at__date__gte=data_inicio)
        if data_fim:
            filtros &= Q(created_at__date__lte=data_fim)
        
        # Filtro de perito
        perito_id = request.query_params.get('perito_id')
        if perito_id:
            filtros &= Q(ocorrencia__perito_atribuido_id=perito_id)
        
        # Filtro de unidade
        unidade_id = request.query_params.get('unidade_id')
        if unidade_id:
            filtros &= Q(unidade_demandante_id=unidade_id)
        
        # Filtro de serviço
        servico_id = request.query_params.get('servico_id')
        if servico_id:
            filtros &= Q(ocorrencia__servico_pericial_id=servico_id)
        
        # Filtro de status
        status_param = request.query_params.get('status')
        if status_param:
            filtros &= Q(status=status_param)
        
        # QuerySet base
        qs = OrdemServico.objects.filter(filtros)
        
        # ✅ CORREÇÃO: Adicionar data atual para verificar vencimentos
        data_atual = timezone.now().date()
        
        # 1. RESUMO GERAL - ✅ CORRIGIDO
        resumo_geral = {
            'total_emitidas': qs.count(),
            'aguardando_ciencia': qs.filter(status='AGUARDANDO_CIENCIA').count(),
            'abertas': qs.filter(status='ABERTA').count(),
            'em_andamento': qs.filter(status='EM_ANDAMENTO').count(),
            'vencidas': qs.filter(
                Q(status__in=['AGUARDANDO_CIENCIA', 'ABERTA', 'EM_ANDAMENTO']) &
                Q(data_prazo__lt=data_atual)
            ).count(),
            'concluidas': qs.filter(status='CONCLUIDA').count(),
        }
        
        # 2. PRODUÇÃO POR PERITO - ✅ CORRIGIDO
        producao_por_perito = qs.values(
            'ocorrencia__perito_atribuido__nome_completo'
        ).annotate(
            total_emitidas=Count('id'),
            concluidas=Count('id', filter=Q(status='CONCLUIDA')),
            em_andamento=Count('id', filter=Q(status='EM_ANDAMENTO')),
            vencidas=Count('id', filter=Q(
                status__in=['AGUARDANDO_CIENCIA', 'ABERTA', 'EM_ANDAMENTO'],
                data_prazo__lt=data_atual
            )),
            aguardando_ciencia=Count('id', filter=Q(status='AGUARDANDO_CIENCIA')),
        ).order_by('-total_emitidas')
        
        producao_detalhada = []
        for perito in producao_por_perito:
            perito_nome = perito['ocorrencia__perito_atribuido__nome_completo']
            
            os_concluidas = qs.filter(
                ocorrencia__perito_atribuido__nome_completo=perito_nome,
                status='CONCLUIDA'
            )
            
            cumpridas_no_prazo = 0
            cumpridas_com_atraso = 0
            
            for os in os_concluidas:
                if os.concluida_com_atraso:
                    cumpridas_com_atraso += 1
                else:
                    cumpridas_no_prazo += 1
            
            producao_detalhada.append({
                'perito': perito_nome or 'Sem perito',
                'total_emitidas': perito['total_emitidas'],
                'concluidas': perito['concluidas'],
                'cumpridas_no_prazo': cumpridas_no_prazo,
                'cumpridas_com_atraso': cumpridas_com_atraso,
                'em_andamento': perito['em_andamento'],
                'vencidas': perito['vencidas'],
                'aguardando_ciencia': perito['aguardando_ciencia'],
                'taxa_cumprimento_prazo': round(
                    (cumpridas_no_prazo / perito['concluidas'] * 100) if perito['concluidas'] > 0 else 0,
                    1
                )
            })
        
        # 3. POR UNIDADE DEMANDANTE - ✅ CORRIGIDO
        por_unidade = qs.values(
            'unidade_demandante__nome'
        ).annotate(
            total=Count('id'),
            concluidas=Count('id', filter=Q(status='CONCLUIDA')),
            em_andamento=Count('id', filter=Q(status='EM_ANDAMENTO')),
            vencidas=Count('id', filter=Q(
                status__in=['AGUARDANDO_CIENCIA', 'ABERTA', 'EM_ANDAMENTO'],
                data_prazo__lt=data_atual
            ))
        ).order_by('-total')
        
        # 4. POR SERVIÇO PERICIAL - ✅ CORRIGIDO
        por_servico = qs.values(
            'ocorrencia__servico_pericial__sigla',
            'ocorrencia__servico_pericial__nome'
        ).annotate(
            total=Count('id'),
            concluidas=Count('id', filter=Q(status='CONCLUIDA')),
            em_andamento=Count('id', filter=Q(status='EM_ANDAMENTO')),
            vencidas=Count('id', filter=Q(
                status__in=['AGUARDANDO_CIENCIA', 'ABERTA', 'EM_ANDAMENTO'],
                data_prazo__lt=data_atual
            ))
        ).order_by('-total')
        
        # 5. REITERAÇÕES
        reiteracoes_stats = {
            'total_originais': qs.filter(numero_reiteracao=0).count(),
            'total_reiteracoes': qs.filter(numero_reiteracao__gt=0).count(),
            'primeira_reiteracao': qs.filter(numero_reiteracao=1).count(),
            'segunda_reiteracao': qs.filter(numero_reiteracao=2).count(),
            'terceira_ou_mais': qs.filter(numero_reiteracao__gte=3).count(),
        }
        
        # 6. TAXA DE CUMPRIMENTO
        os_concluidas_todas = qs.filter(status='CONCLUIDA')
        total_concluidas = os_concluidas_todas.count()
        
        cumpridas_prazo_total = 0
        cumpridas_atraso_total = 0
        
        for os in os_concluidas_todas:
            if os.concluida_com_atraso:
                cumpridas_atraso_total += 1
            else:
                cumpridas_prazo_total += 1
        
        taxa_cumprimento = {
            'total_concluidas': total_concluidas,
            'cumpridas_no_prazo': cumpridas_prazo_total,
            'cumpridas_com_atraso': cumpridas_atraso_total,
            'percentual_no_prazo': round(
                (cumpridas_prazo_total / total_concluidas * 100) if total_concluidas > 0 else 0,
                1
            ),
            'percentual_com_atraso': round(
                (cumpridas_atraso_total / total_concluidas * 100) if total_concluidas > 0 else 0,
                1
            )
        }
        
        # 7. PRAZOS MÉDIOS
        os_com_conclusao = qs.filter(
            status='CONCLUIDA',
            data_ciencia__isnull=False,
            data_conclusao__isnull=False
        )
        
        if os_com_conclusao.exists():
            tempo_medio = os_com_conclusao.annotate(
                dias_para_concluir=ExpressionWrapper(
                    F('data_conclusao') - F('data_ciencia'),
                    output_field=fields.DurationField()
                )
            ).aggregate(
                media=Avg('dias_para_concluir')
            )
            
            if tempo_medio['media']:
                dias_medio = tempo_medio['media'].days
            else:
                dias_medio = 0
        else:
            dias_medio = 0
        
        prazos_stats = {
            'tempo_medio_conclusao_dias': dias_medio,
            'prazo_medio_concedido': round(qs.aggregate(Avg('prazo_dias'))['prazo_dias__avg'] or 0, 1)
        }
        
        # 8. EVOLUÇÃO TEMPORAL
        doze_meses_atras = timezone.now() - timedelta(days=365)
        evolucao_temporal = qs.filter(
            created_at__gte=doze_meses_atras
        ).annotate(
            mes=TruncDate('created_at')
        ).values('mes').annotate(
            total=Count('id'),
            concluidas=Count('id', filter=Q(status='CONCLUIDA'))
        ).order_by('mes')
        
        # RESPOSTA
        return Response({
            'resumo_geral': resumo_geral,
            'producao_por_perito': producao_detalhada,
            'por_unidade_demandante': list(por_unidade),
            'por_servico_pericial': list(por_servico),
            'reiteracoes': reiteracoes_stats,
            'taxa_cumprimento': taxa_cumprimento,
            'prazos': prazos_stats,
            'evolucao_temporal': list(evolucao_temporal)
        })
        
    @action(detail=False, methods=['get'], url_path='relatorios-gerenciais-pdf')
    def relatorios_gerenciais_pdf(self, request):
        """Gera PDF dos relatórios gerenciais"""
        from .pdf_generator import gerar_pdf_relatorios_gerenciais
        
        # Obter dados do relatório
        response_data = self.relatorios_gerenciais(request)
        dados = response_data.data
        
        # Preparar informações de filtros
        filtros_aplicados = {}
        if request.query_params.get('data_inicio'):
            filtros_aplicados['data_inicio'] = request.query_params.get('data_inicio')
        if request.query_params.get('data_fim'):
            filtros_aplicados['data_fim'] = request.query_params.get('data_fim')
        # Adicionar outros filtros conforme necessário
        
        return gerar_pdf_relatorios_gerenciais(dados, filtros_aplicados)