# protocolos/views.py

import io
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from usuarios.models import User
from custodia.models import Vestigio, VestigioMovimentacao
from .models import ProtocoloEntrega
from .permissions import PodeEmitirProtocolo, PodeVerProtocolo
from .serializers import (
    ProtocoloListSerializer,
    ProtocoloDetailSerializer,
    ProtocoloCreateSerializer,
    AssinarProtocoloSerializer,
)
from .filters import ProtocoloEntregaFilter
from .pdf_generator import gerar_protocolo_pdf


# ─── Utilitário: gera número sequencial por ano ───────────────────────────────

def _proximo_numero() -> str:
    ano = timezone.now().year
    ultimo = ProtocoloEntrega.all_objects.filter(
        numero__endswith=f'/{ano}'
    ).order_by('-numero').select_for_update().first()
    if ultimo:
        seq = int(ultimo.numero.split('/')[0]) + 1
    else:
        seq = 1
    return f'{seq:06d}/{ano}'


# ─── Utilitário: mapa de label legível do perfil ──────────────────────────────

_PERFIL_LABEL = {
    'CUSTODIANTE':    'Custodiante',
    'ADMINISTRATIVO': 'Administrativo',
    'SUPER_ADMIN':    'Super Administrador',
    'PERITO':         'Perito Criminal',
    'OPERACIONAL':    'Operacional',
    'EXTERNO':        'Usuário Externo',
}


# ─── ViewSet ──────────────────────────────────────────────────────────────────

class ProtocoloEntregaViewSet(viewsets.ModelViewSet):
    queryset = ProtocoloEntrega.objects.select_related(
        'vestigio', 'ocorrencia', 'procedimento',
        'autoridade__cargo', 'unidade_demandante',
        'entregue_por', 'recebido_por_usuario',
    ).order_by('-created_at')

    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = ProtocoloEntregaFilter
    search_fields = [
        'numero', 'vestigio__lacre', 'vestigio__num_processo_sei',
        'ocorrencia__numero_ocorrencia',
        'recebido_por_nome', 'recebido_por_cpf',
        'autoridade__nome', 'entregue_por__nome_completo',
    ]

    def get_permissions(self):
        if self.action in ('create', 'confirmar_manual'):
            return [PodeEmitirProtocolo()]
        if self.action == 'validar':
            return [AllowAny()]
        if self.action == 'destroy':
            from custodia.permissions import IsSuperAdmin
            return [IsSuperAdmin()]
        return [PodeVerProtocolo()]

    def get_serializer_class(self):
        if self.action == 'list':
            return ProtocoloListSerializer
        return ProtocoloDetailSerializer

    # ── POST /api/protocolos/ ─────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        ser = ProtocoloCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user = request.user

        # 1. Validar vestígio
        try:
            vestigio = Vestigio.objects.select_related(
                'unidade_demandante', 'servico_pericial', 'autoridade', 'user_destino'
            ).get(pk=data['vestigio_id'])
        except Vestigio.DoesNotExist:
            raise ValidationError({'vestigio_id': 'Vestígio não encontrado.'})

        ja_finalizado = (vestigio.status == Vestigio.Status.FINALIZADO)

        # 2. Se não finalizado: exige assinatura digital
        if not ja_finalizado:
            email_ass = data.get('assinatura_email', '').strip().lower()
            senha_ass = data.get('assinatura_senha', '')
            motivo    = data.get('motivo_finalizacao', 'Devolução de material via Protocolo de Saída')

            if not email_ass:
                raise ValidationError({'assinatura_email': 'Obrigatório para finalizar o vestígio.'})
            if not senha_ass:
                raise ValidationError({'assinatura_senha': 'Obrigatório para finalizar o vestígio.'})

            if email_ass != user.email.lower().strip():
                raise ValidationError({'assinatura_email': 'O e-mail não corresponde ao usuário autenticado.'})
            if not user.check_password(senha_ass):
                raise ValidationError({'assinatura_senha': 'Senha incorreta. Assinatura digital não confirmada.'})

        # 3. Validar FKs auxiliares
        from autoridades.models import Autoridade
        from unidades_demandantes.models import UnidadeDemandante

        try:
            autoridade = Autoridade.objects.get(pk=data['autoridade_id'])
        except Autoridade.DoesNotExist:
            raise ValidationError({'autoridade_id': 'Autoridade não encontrada.'})

        try:
            unidade = UnidadeDemandante.objects.get(pk=data['unidade_demandante_id'])
        except UnidadeDemandante.DoesNotExist:
            raise ValidationError({'unidade_demandante_id': 'Unidade demandante não encontrada.'})

        # Ocorrência OBRIGATÓRIA e deve estar vinculada ao vestígio
        from ocorrencias.models import Ocorrencia
        ocorrencia_id = data.get('ocorrencia_id')
        if not ocorrencia_id:
            raise ValidationError({'ocorrencia_id': 'A ocorrência é obrigatória para emitir o protocolo de saída.'})

        try:
            ocorrencia = Ocorrencia.objects.get(pk=ocorrencia_id)
        except Ocorrencia.DoesNotExist:
            raise ValidationError({'ocorrencia_id': 'Ocorrência não encontrada.'})

        ocorrencias_do_vestigio = vestigio.ocorrencias_vinculadas.values_list('id', flat=True)
        if not ocorrencias_do_vestigio.exists():
            raise ValidationError({
                'ocorrencia_id': (
                    'Este vestígio não possui ocorrências vinculadas. '
                    'Vincule uma ocorrência ao vestígio antes de emitir o protocolo.'
                )
            })
        if ocorrencia.pk not in ocorrencias_do_vestigio:
            raise ValidationError({
                'ocorrencia_id': (
                    'A ocorrência selecionada não está vinculada a este vestígio. '
                    'Utilize apenas ocorrências já associadas ao vestígio.'
                )
            })

        procedimento = None
        if data.get('procedimento_id'):
            from procedimentos_cadastrados.models import ProcedimentoCadastrado
            try:
                procedimento = ProcedimentoCadastrado.objects.get(pk=data['procedimento_id'])
            except ProcedimentoCadastrado.DoesNotExist:
                raise ValidationError({'procedimento_id': 'Procedimento não encontrado.'})

        recebido_por_usuario = None
        if data.get('recebido_por_usuario_id'):
            try:
                recebido_por_usuario = User.objects.get(pk=data['recebido_por_usuario_id'])
            except User.DoesNotExist:
                raise ValidationError({'recebido_por_usuario_id': 'Usuário recebedor não encontrado.'})

        # 4. Criar protocolo + (opcional) finalizar vestígio — atômico
        with transaction.atomic():
            numero = _proximo_numero()
            protocolo_hash = ProtocoloEntrega.gerar_hash(numero, vestigio.pk)

            protocolo = ProtocoloEntrega.objects.create(
                numero=numero,
                tipo_entrega=data['tipo_entrega'],
                vestigio=vestigio,
                lacre_na_entrega=data.get('lacre_na_entrega') or vestigio.lacre or '',
                descricao_material=data['descricao_material'],
                ocorrencia=ocorrencia,
                procedimento=procedimento,
                autoridade=autoridade,
                unidade_demandante=unidade,
                entregue_por=user,
                entregue_por_nome=user.nome_completo,
                entregue_por_cargo=_PERFIL_LABEL.get(user.perfil, user.perfil or ''),
                entregue_por_cpf=user.cpf or '',
                entregue_em=timezone.now(),
                recebido_por_nome=data['recebido_por_nome'],
                recebido_por_cargo=data['recebido_por_cargo'],
                recebido_por_cpf=data.get('recebido_por_cpf', ''),
                recebido_por_matricula=data.get('recebido_por_matricula', ''),
                recebido_por_usuario=recebido_por_usuario,
                status_recebimento=ProtocoloEntrega.StatusRecebimento.PENDENTE,
                protocolo_hash=protocolo_hash,
                vestigio_foi_finalizado=not ja_finalizado,
                observacoes=data.get('observacoes', ''),
                created_by=user,
            )

            if not ja_finalizado:
                motivo_completo = f'{motivo} — Protocolo de Saída nº {numero}'
                vestigio.status = Vestigio.Status.FINALIZADO
                vestigio.saiu_da_custodia = True
                vestigio.motivo_finalizacao = motivo_completo
                vestigio.updated_by = user
                vestigio.save()

                # Movimentação de finalização (espelho do finalizar() da custódia)
                ultima_mov = VestigioMovimentacao.objects.filter(
                    vestigio=vestigio
                ).order_by('-created_at').first()

                if ultima_mov:
                    VestigioMovimentacao.objects.create(
                        vestigio=vestigio,
                        lacre=ultima_mov.lacre,
                        num_processo_sei=ultima_mov.num_processo_sei,
                        descricao=motivo_completo,
                        unidade_demandante=ultima_mov.unidade_demandante,
                        servico_pericial=ultima_mov.servico_pericial,
                        autoridade=ultima_mov.autoridade,
                        user_destino=ultima_mov.user_destino,
                        aceito=True,
                        data_hora_aceito=timezone.now(),
                        created_by=user,
                    )

        protocolo.refresh_from_db()
        return Response(
            {
                'protocolo': ProtocoloDetailSerializer(protocolo).data,
                'vestigio_foi_finalizado': protocolo.vestigio_foi_finalizado,
                'mensagem': (
                    f'Protocolo {numero} emitido. Vestígio finalizado automaticamente.'
                    if protocolo.vestigio_foi_finalizado
                    else f'Protocolo {numero} emitido. Vestígio já estava finalizado.'
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    # ── GET /api/protocolos/{id}/pdf/ ─────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        protocolo = self.get_object()
        buf = io.BytesIO()
        gerar_protocolo_pdf(protocolo, buf)
        buf.seek(0)
        nome = f'protocolo_{protocolo.numero.replace("/", "_")}.pdf'
        return FileResponse(buf, content_type='application/pdf', as_attachment=False, filename=nome)

    # ── POST /api/protocolos/{id}/assinar/ ────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='assinar')
    def assinar(self, request, pk=None):
        """Recebedor assina eletronicamente com email+senha."""
        protocolo = self.get_object()

        if protocolo.status_recebimento != ProtocoloEntrega.StatusRecebimento.PENDENTE:
            raise ValidationError({'detail': 'Este protocolo já foi recebido.'})

        ser = AssinarProtocoloSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user

        email_ass = ser.validated_data['assinatura_email'].lower().strip()
        senha_ass = ser.validated_data['assinatura_senha']

        if email_ass != user.email.lower().strip():
            raise ValidationError({'assinatura_email': 'O e-mail não corresponde ao usuário autenticado.'})
        if not user.check_password(senha_ass):
            raise ValidationError({'assinatura_senha': 'Senha incorreta.'})

        # ── BLOQUEIO DE SEGURANÇA: Evita que o usuário B assine o protocolo emitido para o usuário A ── [14]
        # 1. Se o protocolo já foi explicitamente destinado a uma conta do sistema por FK
        if protocolo.recebido_por_usuario and user != protocolo.recebido_por_usuario:
            raise ValidationError({
                'detail': (
                    f'Assinatura negada. Este protocolo foi destinado exclusivamente para '
                    f'{protocolo.recebido_por_usuario.nome_completo}, mas você está autenticado '
                    f'como {user.nome_completo}.'
                )
            })

        # 2. Se o protocolo foi preenchido com CPF manual, comparamos os CPFs de forma limpa (sem traço/ponto)
        if protocolo.recebido_por_cpf:
            user_cpf_limpo = ''.join(filter(str.isdigit, user.cpf or ''))
            proto_cpf_limpo = ''.join(filter(str.isdigit, protocolo.recebido_por_cpf or ''))
            
            if proto_cpf_limpo and user_cpf_limpo != proto_cpf_limpo:
                raise ValidationError({
                    'detail': (
                        f'Assinatura negada. Este protocolo foi emitido para o CPF '
                        f'{protocolo.recebido_por_cpf} (Destinatário: {protocolo.recebido_por_nome}), '
                        f'mas você está autenticado como {user.nome_completo} (CPF {user.cpf or "Não cadastrado"}).'
                    )
                })

        # 3. Se passou pelas validações, autoriza a assinatura eletrônica
        protocolo.status_recebimento = ProtocoloEntrega.StatusRecebimento.ASSINADO_ELETRONICAMENTE
        protocolo.recebido_por_usuario = user
        protocolo.recebido_em = timezone.now()
        protocolo.updated_by = user
        protocolo.save()

        return Response(ProtocoloDetailSerializer(protocolo).data)

    # ── POST /api/protocolos/{id}/confirmar-manual/ ───────────────────────────

    @action(detail=True, methods=['post'], url_path='confirmar-manual', permission_classes=[PodeEmitirProtocolo])
    def confirmar_manual(self, request, pk=None):
        """Custodiante confirma que o recebedor assinou no papel."""
        protocolo = self.get_object()

        if protocolo.status_recebimento != ProtocoloEntrega.StatusRecebimento.PENDENTE:
            raise ValidationError({'detail': 'Este protocolo já foi recebido.'})

        protocolo.status_recebimento = ProtocoloEntrega.StatusRecebimento.ASSINADO_MANUAL
        protocolo.recebido_em = timezone.now()
        protocolo.updated_by = request.user
        protocolo.save()

        return Response(ProtocoloDetailSerializer(protocolo).data)

    # ── GET /api/protocolos/validar/?protocolo=XXXX ───────────────────────────

    @action(detail=False, methods=['get'], url_path='validar', permission_classes=[AllowAny])
    def validar(self, request):
        hash_param = request.query_params.get('protocolo', '').strip()
        if not hash_param:
            return Response({'valido': False, 'detalhe': 'Parâmetro ?protocolo= ausente.'}, status=400)

        try:
            p = ProtocoloEntrega.objects.select_related(
                'vestigio', 'entregue_por', 'unidade_demandante', 'autoridade'
            ).get(protocolo_hash=hash_param)
        except ProtocoloEntrega.DoesNotExist:
            return Response({'valido': False, 'detalhe': 'Protocolo não encontrado ou hash inválido.'})

        return Response({
            'valido': True,
            'numero': p.numero,
            'tipo_entrega': p.get_tipo_entrega_display(),
            'vestigio_lacre': p.vestigio.lacre,
            'vestigio_status_atual': p.vestigio.status,
            'recebido_por': p.recebido_por_nome,
            'status_recebimento': p.get_status_recebimento_display(),
            'emitido_por': p.entregue_por_nome,
            'emitido_em': p.entregue_em,
            'unidade': p.unidade_demandante.nome,
        })