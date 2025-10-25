# ordens_servico/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
# Imports necessários (verificados e completos)
from django.db.models import Count, Q, Avg, F, ExpressionWrapper, fields, Sum, DateField # ✅ DateField adicionado/confirmado
from django.db.models.functions import TruncDate
from datetime import timedelta
from django.core.exceptions import ValidationError # Para try/except em reiterar

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
# Import User model
from django.contrib.auth import get_user_model
User = get_user_model()


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

    # --- MÉTODO get_queryset ORIGINAL ---
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
            # Assume deleted_at existe
            return queryset.filter(deleted_at__isnull=False)

        # Demais actions só mostram não-deletados
        queryset = queryset.filter(deleted_at__isnull=True)

        # Super Admin e Admin veem todas as OS
        # Assume perfil existe no user model
        if user.is_superuser or getattr(user, 'perfil', None) == 'ADMINISTRATIVO':
            return queryset

        # Perito vê apenas as OS de ocorrências que lhe foram atribuídas
        if getattr(user, 'perfil', None) == 'PERITO':
            return queryset.filter(ocorrencia__perito_atribuido=user)

        # Outros perfis (se houver) - depende da permission class
        return queryset

    # --- MÉTODO get_serializer_class ORIGINAL ---
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

    # --- MÉTODO create ORIGINAL ---
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
        except (ValueError, TypeError):
             return Response({"error": "ID de ocorrência inválido."}, status=status.HTTP_400_BAD_REQUEST)


        # Validações de negócio (mantendo as respostas de erro originais)
        if hasattr(Ocorrencia, 'Status') and ocorrencia.status == Ocorrencia.Status.FINALIZADA:
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
        try:
             ordem_servico = serializer.save()
        except Exception as e:
             # Logar erro e retornar 500
             print(f"Erro no serializer.save() ao criar OS: {e}")
             return Response({"error": "Erro interno ao salvar a Ordem de Serviço."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

    # --- MÉTODO retrieve ORIGINAL ---
    def retrieve(self, request, *args, **kwargs):
        """
        Retorna detalhes de uma OS.
        Registra visualização automaticamente para o perito.
        """
        instance = self.get_object()

        # Registra visualização se for o perito destinatário
        if (instance.ocorrencia and instance.ocorrencia.perito_atribuido and
            request.user.is_authenticated and
            request.user.id == instance.ocorrencia.perito_atribuido.id and
            hasattr(instance, 'registrar_visualizacao')): # Verifica se o método existe
            instance.registrar_visualizacao()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # --- MÉTODO perform_update ORIGINAL ---
    def perform_update(self, serializer):
        """Registra quem atualizou"""
        serializer.save(updated_by=self.request.user)

    # --- MÉTODO destroy ORIGINAL ---
    def destroy(self, request, *args, **kwargs):
        """Soft delete - só Super Admin pode deletar"""
        instance = self.get_object()
        # Assume que o AuditModel tem o método soft_delete
        if hasattr(instance, 'soft_delete'):
            instance.soft_delete(user=request.user)
            return Response(
                {'message': f'OS {instance.numero_os} movida para a lixeira.'},
                status=status.HTTP_204_NO_CONTENT
            )
        else:
            # Fallback ou erro se soft_delete não existir
            return Response({"error": "Operação de exclusão não suportada."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


    # =========================================================================
    # ACTIONS CUSTOMIZADAS (Existentes - Mantidas EXATAMENTE como no seu código original)
    # =========================================================================

    @action(detail=False, methods=['get'], url_path='pendentes-ciencia')
    def pendentes_ciencia(self, request):
        """
        Retorna a quantidade de OS aguardando ciência do perito logado
        ✅ CORRIGIDO (Risco 5): Removidos 'print()' de debug.
        """
        user = request.user

        # APENAS PERITOS veem o banner
        # Assume 'perfil' existe no user model
        if getattr(user, 'perfil', None) != 'PERITO':
            return Response({'count': 0, 'ordens': []})

        # Busca OS aguardando ciência DO PERITO LOGADO
        # Assume 'deleted_at' existe
        ordens = OrdemServico.objects.filter(
            status='AGUARDANDO_CIENCIA',
            ocorrencia__perito_atribuido=user,
            deleted_at__isnull=True
        ).select_related('ocorrencia').order_by('-created_at')

        # Serializa dados mínimos
        dados = []
        for os in ordens:
            dados.append({
                'id': os.id,
                'numero_os': os.numero_os,
                # Assume 'dias_desde_emissao' existe
                'dias_desde_emissao': getattr(os, 'dias_desde_emissao', None),
                'created_at': os.created_at.isoformat() if os.created_at else None
            })

        return Response({
            'count': ordens.count(),
            'ordens': dados
        })

    @action(detail=True, methods=['post'], url_path='tomar-ciencia')
    def tomar_ciencia(self, request, pk=None, **kwargs):
        """Permite que o perito registre ciência da OS com assinatura digital"""
        ordem_servico = self.get_object()

        # Validações (mantendo respostas de erro originais)
        if not ordem_servico.ocorrencia or request.user != ordem_servico.ocorrencia.perito_atribuido:
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
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Registra ciência
        ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1') # Default IP
        try:
             # Assume que o método tomar_ciencia existe no model
            ordem_servico.tomar_ciencia(user=request.user, ip_address=ip_address)
        except Exception as e:
             # Log e erro genérico
             print(f"Erro ao chamar ordem_servico.tomar_ciencia: {e}")
             return Response({"error": "Erro interno ao registrar ciência."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        # from django.core.exceptions import ValidationError # Já importado no topo

        os_anterior = self.get_object()

        # Valida assinatura
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Remove dados de assinatura
        validated_data = serializer.validated_data.copy()
        validated_data.pop('email', None)
        validated_data.pop('password', None)

        # Captura ValidationError para retornar mensagem amigável (mantendo lógica original)
        try:
            # Busca objeto User para 'ordenada_por'
            ordenada_por_obj = None
            ordenada_por_id_val = validated_data.get('ordenada_por_id')
            if ordenada_por_id_val:
                 try:
                      # Assume que 'ordenada_por_id' no serializer valida que é um PK válido
                      ordenada_por_obj = User.objects.get(pk=ordenada_por_id_val)
                 except User.DoesNotExist:
                      # Se o serializer não validou, levantamos erro aqui
                      raise ValidationError("Usuário 'ordenada por' selecionado não existe.")

            # Cria reiteração (assume método existe no model)
            nova_os = os_anterior.reiterar(
                prazo_dias=validated_data['prazo_dias'],
                ordenada_por=ordenada_por_obj, # Passa o objeto User ou None
                user=request.user,
                observacoes=validated_data.get('observacoes_administrativo', '')
            )
        except ValidationError as e:
            # Retorna erro 400 com a mensagem do ValidationError
            error_message = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return Response({'error': error_message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
             # Log e erro genérico
             print(f"Erro inesperado ao reiterar OS: {e}")
             return Response({"error": "Erro interno ao criar reiteração."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

        # Validações (mantendo respostas de erro originais)
        if not ordem_servico.ocorrencia or request.user != ordem_servico.ocorrencia.perito_atribuido:
            return Response(
                {"error": "Apenas o perito atribuído pode iniciar o trabalho."},
                status=status.HTTP_403_FORBIDDEN
            )

        if ordem_servico.status != OrdemServico.Status.ABERTA:
            status_atual = ordem_servico.get_status_display()
            detalhes = f"O status atual é '{status_atual}'. Você só pode iniciar trabalho em ordens com status 'Aberta'."
            acao = "Verifique o status da ordem e o fluxo correto."
            if ordem_servico.status == OrdemServico.Status.AGUARDANDO_CIENCIA:
                detalhes = "Você precisa tomar ciência da Ordem de Serviço antes de iniciar o trabalho."
                acao = "Clique em 'Tomar Ciência' primeiro, depois você poderá iniciar o trabalho."
            elif ordem_servico.status == OrdemServico.Status.EM_ANDAMENTO:
                detalhes = "Esta ordem já está com o trabalho iniciado."
                acao = "Não é necessário iniciar novamente. Continue trabalhando na OS."
            elif ordem_servico.status == OrdemServico.Status.CONCLUIDA:
                detalhes = "Esta ordem já foi concluída."
                acao = "Não é possível iniciar trabalho em uma OS já concluída."
            # else: # Se houver outros status futuros

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

        # Inicia trabalho (assume método existe no model)
        try:
             ordem_servico.iniciar_trabalho(user=request.user)
        except Exception as e:
             print(f"Erro ao chamar ordem_servico.iniciar_trabalho: {e}")
             return Response({"error": "Erro interno ao iniciar trabalho."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # Retorna resposta
        serializer = self.get_serializer(ordem_servico) # Usa serializer padrão
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

        # Validações (mantendo respostas de erro originais)
        if not ordem_servico.ocorrencia or request.user != ordem_servico.ocorrencia.perito_atribuido:
            return Response(
                {"error": "Apenas o perito atribuído pode justificar atraso."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Usa a property 'esta_vencida' do model
        if not getattr(ordem_servico, 'esta_vencida', False):
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
        serializer = self.get_serializer(data=request.data) # Usa JustificarAtrasoSerializer
        serializer.is_valid(raise_exception=True)

        try:
            # Assume método existe no model
            ordem_servico.justificar_atraso(
                justificativa=serializer.validated_data['justificativa'],
                user=request.user
            )
        except Exception as e:
             print(f"Erro ao chamar ordem_servico.justificar_atraso: {e}")
             return Response({"error": "Erro interno ao salvar justificativa."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        (Mantendo respostas de erro originais)
        """
        ordem_servico = self.get_object()

        # VALIDAÇÃO 1: Apenas administrativos
        user_perfil = getattr(request.user, 'perfil', None)
        if not request.user.is_superuser and user_perfil not in ['ADMINISTRATIVO']:
            return Response(
                {'error': 'Apenas administrativos podem concluir ordens de serviço.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # VALIDAÇÃO 2: Não pode concluir OS já concluída
        if ordem_servico.status == OrdemServico.Status.CONCLUIDA:
            return Response(
                {'error': 'Esta ordem de serviço já está concluída.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # VALIDAÇÃO 3: Perito deve ter tomado ciência (via status)
        if ordem_servico.status == OrdemServico.Status.AGUARDANDO_CIENCIA:
            perito_nome = "o perito"
            if ordem_servico.ocorrencia and ordem_servico.ocorrencia.perito_atribuido:
                 perito_nome = ordem_servico.ocorrencia.perito_atribuido.nome_completo or perito_nome
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

        # VALIDAÇÃO 4: Verificar se tem ciência (via campo ciente_por - mais direto)
        if not ordem_servico.ciente_por:
            perito_nome = "o perito"
            if ordem_servico.ocorrencia and ordem_servico.ocorrencia.perito_atribuido:
                 perito_nome = ordem_servico.ocorrencia.perito_atribuido.nome_completo or perito_nome
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

        # CONCLUI A OS (assume método concluir existe no model)
        try:
             ordem_servico.concluir(user=request.user)
        except Exception as e:
             print(f"Erro ao chamar ordem_servico.concluir: {e}")
             return Response({"error": "Erro interno ao concluir a OS."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # RETORNA SUCESSO
        serializer = self.get_serializer(ordem_servico) # Serializer padrão
        return Response(
            {
                'message': f'OS {ordem_servico.numero_os} concluída com sucesso!',
                'ordem_servico': serializer.data
            },
            status=status.HTTP_200_OK
        )

    # =========================================================================
    # LIXEIRA E RESTAURAÇÃO (Mantendo código original)
    # =========================================================================

    @action(detail=False, methods=['get'])
    def lixeira(self, request, **kwargs):
        """Lista as OS deletadas (soft delete)"""
        queryset = self.filter_queryset(self.get_queryset()) # get_queryset deve retornar os deletados aqui
        page = self.paginate_queryset(queryset)
        if page is not None:
             serializer = self.get_serializer(page, many=True) # Usa OrdemServicoLixeiraSerializer
             return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, **kwargs):
        """Restaura uma OS da lixeira"""
        # Tenta obter o objeto incluindo deletados
        try:
             lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
             filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
             # Assume que all_objects existe e inclui deletados
             if hasattr(OrdemServico, 'all_objects'):
                  instance = OrdemServico.all_objects.get(**filter_kwargs)
             else: # Fallback se não tiver all_objects
                  instance = OrdemServico.objects.get(**filter_kwargs) # Pode falhar se o manager padrão exclui
        except OrdemServico.DoesNotExist:
             return Response({"error": "OS não encontrada."}, status=status.HTTP_404_NOT_FOUND)

        # Assume deleted_at existe
        if not getattr(instance, 'deleted_at', None):
            return Response({'message': 'Esta OS não está na lixeira.'}, status=status.HTTP_400_BAD_REQUEST)

        # Assume restore existe
        if hasattr(instance, 'restore'):
             try: instance.restore()
             except Exception as e: return Response({"error": f"Erro interno ao restaurar: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
             serializer = OrdemServicoSerializer(instance, context={'request': request}) # Retorna com serializer completo
             return Response({ 'message': f'OS {instance.numero_os} restaurada com sucesso.', 'ordem_servico': serializer.data }, status=status.HTTP_200_OK)
        else: return Response({"error": "Operação de restauração não suportada."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


    # =========================================================================
    # GERAÇÃO DE PDFs (Mantendo código original)
    # =========================================================================

    @action(detail=True, methods=['get'], url_path='pdf')
    def gerar_pdf(self, request, pk=None):
        """Gera PDF simples da OS"""
        ordem = self.get_object()
        user_perfil = getattr(request.user, 'perfil', None)

        if request.user.is_superuser or user_perfil in ['ADMINISTRATIVO']:
            return gerar_pdf_ordem_servico(ordem, request)

        is_perito_dest = (ordem.ocorrencia and ordem.ocorrencia.perito_atribuido and request.user.id == ordem.ocorrencia.perito_atribuido.id)

        # Assume ocultar_detalhes_ate_ciencia existe
        if is_perito_dest and hasattr(ordem, 'ocultar_detalhes_ate_ciencia') and ordem.ocultar_detalhes_ate_ciencia():
            return Response({'error': 'Você precisa tomar ciência da OS antes de gerar o PDF.'}, status=status.HTTP_403_FORBIDDEN)
        elif is_perito_dest:
            return gerar_pdf_ordem_servico(ordem, request)
        else:
            return Response({'error': 'Permissão negada.'}, status=status.HTTP_403_FORBIDDEN)


    @action(detail=True, methods=['get'], url_path='pdf-oficial')
    def gerar_pdf_oficial(self, request, *args, **kwargs):
        """Gera PDF oficial da OS para impressão/assinatura"""
        ordem_servico = self.get_object()
        user_perfil = getattr(request.user, 'perfil', None)

        if request.user.is_superuser or user_perfil in ['ADMINISTRATIVO']:
            return gerar_pdf_oficial_ordem_servico(ordem_servico, request)

        is_perito_dest = (ordem_servico.ocorrencia and ordem_servico.ocorrencia.perito_atribuido and request.user.id == ordem_servico.ocorrencia.perito_atribuido.id)

        if is_perito_dest and hasattr(ordem_servico, 'ocultar_detalhes_ate_ciencia') and ordem_servico.ocultar_detalhes_ate_ciencia():
            return Response({'error': 'Você precisa tomar ciência da OS antes de gerar o PDF oficial.'}, status=status.HTTP_403_FORBIDDEN)
        elif is_perito_dest:
             return gerar_pdf_oficial_ordem_servico(ordem_servico, request)
        else:
             return Response({'error': 'Permissão negada.'}, status=status.HTTP_403_FORBIDDEN)


    @action(detail=False, methods=['get'], url_path='listagem-pdf')
    def gerar_listagem_pdf(self, request, *args, **kwargs):
        """Gera PDF com todas as OS de uma ocorrência"""
        ocorrencia_id = request.query_params.get('ocorrencia_id')

        if not ocorrencia_id:
            return Response({"error": "Query param 'ocorrencia_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Adicionar verificação de permissão se Ocorrencia tiver regras
            ocorrencia = Ocorrencia.objects.get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            return Response({"error": "Ocorrência não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        except (ValueError, TypeError):
             return Response({"error": "ID de ocorrência inválido."}, status=status.HTTP_400_BAD_REQUEST)

        return gerar_pdf_listagem_ordens_servico(ocorrencia, request)

    # =========================================================================
    # RELATÓRIOS (Mantendo versão otimizada e com correção do TruncDate)
    # =========================================================================
    @action(detail=False, methods=['get'], url_path='relatorios-gerenciais')
    def relatorios_gerenciais(self, request):
        """ Retorna relatórios gerenciais agregados sobre Ordens de Serviço. """
        queryset_filtrado = self.filter_queryset(self.get_queryset())
        data_atual = timezone.now().date()

        # 1. RESUMO GERAL
        resumo_geral = queryset_filtrado.aggregate(
            total_emitidas=Count('id'), aguardando_ciencia=Count('id', filter=Q(status='AGUARDANDO_CIENCIA')),
            abertas=Count('id', filter=Q(status='ABERTA')), em_andamento=Count('id', filter=Q(status='EM_ANDAMENTO')),
            vencidas=Count('id', filter=Q(data_prazo__isnull=False, data_prazo__lt=data_atual) & ~Q(status='CONCLUIDA')),
            concluidas=Count('id', filter=Q(status='CONCLUIDA')),
        )

        # 2. PRODUÇÃO POR PERITO
        producao_por_perito = queryset_filtrado.values('ocorrencia__perito_atribuido__nome_completo').annotate(
            perito_id=F('ocorrencia__perito_atribuido_id'), total_emitidas=Count('id'), concluidas=Count('id', filter=Q(status='CONCLUIDA')),
            em_andamento=Count('id', filter=Q(status='EM_ANDAMENTO')), vencidas=Count('id', filter=Q(data_prazo__isnull=False, data_prazo__lt=data_atual) & ~Q(status='CONCLUIDA')),
            aguardando_ciencia=Count('id', filter=Q(status='AGUARDANDO_CIENCIA')), cumpridas_no_prazo=Count('id', filter=Q(status='CONCLUIDA', data_conclusao__date__lte=F('data_prazo'))),
            cumpridas_com_atraso=Count('id', filter=Q(status='CONCLUIDA', data_conclusao__date__gt=F('data_prazo')))
        ).order_by('-total_emitidas')

        producao_detalhada = []
        for p_data in producao_por_perito:
            conc = p_data['concluidas']; c_np = p_data['cumpridas_no_prazo']
            producao_detalhada.append({ 'perito_id': p_data['perito_id'], 'perito': p_data['ocorrencia__perito_atribuido__nome_completo'] or 'Sem perito', **p_data, 'taxa_cumprimento_prazo': round((c_np / conc * 100) if conc > 0 else 0, 1) })

        # 3. POR UNIDADE DEMANDANTE
        por_unidade = queryset_filtrado.values('unidade_demandante__nome').annotate(
            unidade_id=F('unidade_demandante_id'), total=Count('id'), concluidas=Count('id', filter=Q(status='CONCLUIDA')),
            em_andamento=Count('id', filter=Q(status='EM_ANDAMENTO')), vencidas=Count('id', filter=Q(data_prazo__isnull=False, data_prazo__lt=data_atual) & ~Q(status='CONCLUIDA'))
        ).order_by('-total')

        # 4. POR SERVIÇO PERICIAL
        por_servico = queryset_filtrado.values('ocorrencia__servico_pericial__sigla', 'ocorrencia__servico_pericial__nome').annotate(
            servico_id=F('ocorrencia__servico_pericial_id'), total=Count('id'), concluidas=Count('id', filter=Q(status='CONCLUIDA')),
            em_andamento=Count('id', filter=Q(status='EM_ANDAMENTO')), vencidas=Count('id', filter=Q(data_prazo__isnull=False, data_prazo__lt=data_atual) & ~Q(status='CONCLUIDA'))
        ).order_by('-total')

        # 5. REITERAÇÕES
        reiteracoes_stats = queryset_filtrado.aggregate(
            total_originais=Count('id', filter=Q(numero_reiteracao=0)), total_reiteracoes=Count('id', filter=Q(numero_reiteracao__gt=0)),
            primeira_reiteracao=Count('id', filter=Q(numero_reiteracao=1)), segunda_reiteracao=Count('id', filter=Q(numero_reiteracao=2)),
            terceira_ou_mais=Count('id', filter=Q(numero_reiteracao__gte=3)), total_emitidas=Count('id')
        )

        # 6. TAXA DE CUMPRIMENTO
        taxa_aggr = queryset_filtrado.aggregate(
             total_concluidas=Count('id', filter=Q(status='CONCLUIDA')), cumpridas_no_prazo=Count('id', filter=Q(status='CONCLUIDA', data_conclusao__date__lte=F('data_prazo'))),
             cumpridas_com_atraso=Count('id', filter=Q(status='CONCLUIDA', data_conclusao__date__gt=F('data_prazo')))
        )
        tc_geral = taxa_aggr['total_concluidas']; cnp_geral = taxa_aggr['cumpridas_no_prazo']; cca_geral = taxa_aggr['cumpridas_com_atraso']
        taxa_cumprimento = { 'total_concluidas': tc_geral, 'cumpridas_no_prazo': cnp_geral, 'cumpridas_com_atraso': cca_geral,
            'percentual_no_prazo': round((cnp_geral / tc_geral * 100) if tc_geral > 0 else 0, 1),
            'percentual_com_atraso': round((cca_geral / tc_geral * 100) if tc_geral > 0 else 0, 1) }

        # 7. PRAZOS MÉDIOS
        prazos_aggr = queryset_filtrado.filter( status='CONCLUIDA', data_ciencia__isnull=False, data_conclusao__isnull=False ).annotate(
            duracao=ExpressionWrapper(F('data_conclusao') - F('data_ciencia'), output_field=fields.DurationField())
        ).aggregate( media_duracao=Avg('duracao'), media_prazo_concedido=Avg('prazo_dias') )
        dias_medio = prazos_aggr.get('media_duracao').days if prazos_aggr.get('media_duracao') else 0
        prazos_stats = { 'tempo_medio_conclusao_dias': dias_medio, 'prazo_medio_concedido': round(prazos_aggr.get('media_prazo_concedido') or 0, 1) }

        # 8. EVOLUÇÃO TEMPORAL
        doze_meses_atras = timezone.now().date() - timedelta(days=365)
        evolucao_temporal = queryset_filtrado.filter(created_at__date__gte=doze_meses_atras).annotate(
            # ✅✅✅ CORREÇÃO APLICADA AQUI ✅✅✅
            mes=TruncDate('created_at', kind='month', output_field=DateField()) # Usa kind='month'
        ).values('mes').annotate( total=Count('id'), concluidas=Count('id', filter=Q(status='CONCLUIDA')) ).order_by('mes')

        return Response({
            'resumo_geral': resumo_geral, 'producao_por_perito': producao_detalhada, 'por_unidade_demandante': list(por_unidade),
            'por_servico_pericial': list(por_servico), 'reiteracoes': reiteracoes_stats, 'taxa_cumprimento': taxa_cumprimento,
            'prazos': prazos_stats, 'evolucao_temporal': [{'mes': item['mes'].isoformat(), 'total': item['total'], 'concluidas': item['concluidas']} for item in evolucao_temporal]
        })

    @action(detail=False, methods=['get'], url_path='relatorios-gerenciais-pdf')
    def relatorios_gerenciais_pdf(self, request):
        """Gera PDF dos relatórios gerenciais"""
        from .pdf_generator import gerar_pdf_relatorios_gerenciais

        response = self.relatorios_gerenciais(request)
        if response.status_code != 200: return Response({"error": "Dados indisponíveis para PDF."}, status=response.status_code)
        dados = response.data
        filtros_aplicados = {}
        if request.query_params.get('data_inicio'): filtros_aplicados['Data Início'] = request.query_params.get('data_inicio')
        if request.query_params.get('data_fim'): filtros_aplicados['Data Fim'] = request.query_params.get('data_fim')
        if request.query_params.get('status'): filtros_aplicados['Status'] = request.query_params.get('status')
        perito_id_param = request.query_params.get('perito_id')
        if perito_id_param:
            try: perito = User.objects.get(pk=perito_id_param); filtros_aplicados['Perito'] = perito.nome_completo
            except User.DoesNotExist: filtros_aplicados['Perito'] = f"ID {perito_id_param}"
        # Adicionar busca nome Unidade/Serviço se necessário
        # ...
        usuario_emissor = request.user
        try: return gerar_pdf_relatorios_gerenciais(dados, filtros_aplicados, usuario_emissor)
        except Exception as e: print(f"Erro PDF: {e}"); return Response({"error": "Erro interno ao gerar PDF."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # =========================================================================
    # ✅✅✅ NOVA ACTION PARA ESTATÍSTICAS DO DASHBOARD ✅✅✅
    # =========================================================================
    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas_os(self, request):
        """
        Retorna estatísticas agregadas sobre Ordens de Serviço para o dashboard.
        Filtra automaticamente por perito logado (se for perito).
        Aceita filtro opcional por ?servico_id= via query param.
        """
        user = request.user
        # get_queryset() já aplica filtro base de usuário e não deletados
        # filter_queryset() aplica filtros do FilterSet (como ?ocorrencia_id=, ?status=, etc., se vierem na request)
        queryset = self.filter_queryset(self.get_queryset())

        # Aplica filtro adicional de serviço_id se fornecido na URL E se não foi coberto pelo FilterSet
        servico_id = request.query_params.get('servico_id')
        # Verifica se o filtro já existe no FilterSet para evitar aplicar duas vezes
        filterset_fields = self.filterset_class.get_fields() if self.filterset_class else {}
        if servico_id and 'ocorrencia__servico_pericial' not in filterset_fields and 'servico_id' not in filterset_fields: # Ajuste chave se necessário
            try:
                queryset = queryset.filter(ocorrencia__servico_pericial_id=int(servico_id))
            except (ValueError, TypeError):
                pass # Ignora filtro inválido

        hoje = timezone.now().date()

        # Faz as agregações no queryset já filtrado
        stats = queryset.aggregate(
            total=Count('id'),
            aguardando_ciencia=Count('id', filter=Q(status=OrdemServico.Status.AGUARDANDO_CIENCIA)),
            abertas=Count('id', filter=Q(status=OrdemServico.Status.ABERTA)),
            em_andamento=Count('id', filter=Q(status=OrdemServico.Status.EM_ANDAMENTO)),
            concluidas=Count('id', filter=Q(status=OrdemServico.Status.CONCLUIDA)),
            # Vencidas: Não concluídas E (data_prazo existe E data_prazo < hoje)
            vencidas=Count('id', filter=
                Q(data_prazo__isnull=False) &
                Q(data_prazo__lt=hoje) &
                ~Q(status=OrdemServico.Status.CONCLUIDA) # Exclui as concluídas
            )
        )

        # Formata a resposta baseado no perfil
        user_perfil = getattr(user, 'perfil', None)
        resposta = {} # Resposta padrão vazia

        # Cria dicionário com os resultados, usando get com default 0
        stats_dict = {
           'total': stats.get('total', 0),
           'aguardando_ciencia': stats.get('aguardando_ciencia', 0),
           'abertas': stats.get('abertas', 0),
           'em_andamento': stats.get('em_andamento', 0),
           'vencidas': stats.get('vencidas', 0),
           'concluidas': stats.get('concluidas', 0),
        }

        # Define a chave principal baseada no perfil
        if user_perfil == 'PERITO':
            resposta = {'minhas_os': stats_dict}
        elif user.is_superuser or user_perfil in ['ADMINISTRATIVO', 'OPERACIONAL']:
             resposta = {'geral_os': stats_dict}
        # Outros perfis recebem resposta vazia

        return Response(resposta)

# Fim da classe OrdemServicoViewSet