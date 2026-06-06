# protocolos/serializers.py

from rest_framework import serializers
from .models import ProtocoloEntrega
from custodia.models import Vestigio
from ocorrencias.models import Ocorrencia
from procedimentos_cadastrados.models import ProcedimentoCadastrado
from autoridades.models import Autoridade
from unidades_demandantes.models import UnidadeDemandante


# ─── Serializers de leitura ────────────────────────────────────────────────────

class _VestigioResumo(serializers.Serializer):
    id = serializers.IntegerField()
    lacre = serializers.CharField()
    num_processo_sei = serializers.CharField()
    status = serializers.CharField()
    ocorrencia = serializers.CharField()
    ano_ocorrencia = serializers.IntegerField()


class _OcorrenciaResumo(serializers.Serializer):
    id = serializers.IntegerField()
    numero_ocorrencia = serializers.CharField()
    ano_fato = serializers.IntegerField(source='data_fato.year', default=None)


class _ProcedimentoResumo(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    sigla = serializers.CharField()


class _AutoridadeResumo(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    cargo_nome = serializers.SerializerMethodField()

    def get_cargo_nome(self, obj):
        return obj.cargo.nome if obj.cargo else None


class _UnidadeResumo(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    sigla = serializers.CharField()


class _UsuarioResumo(serializers.Serializer):
    id = serializers.IntegerField()
    nome_completo = serializers.CharField()
    email = serializers.EmailField()
    perfil = serializers.CharField()


class ProtocoloListSerializer(serializers.ModelSerializer):
    vestigio_id = serializers.IntegerField(source='vestigio.id', read_only=True)
    vestigio_lacre = serializers.CharField(source='vestigio.lacre', read_only=True)
    vestigio_status = serializers.CharField(source='vestigio.status', read_only=True)
    ocorrencia_numero = serializers.CharField(source='ocorrencia.numero_ocorrencia', read_only=True)
    unidade_nome = serializers.CharField(source='unidade_demandante.nome', read_only=True)
    unidade_sigla = serializers.CharField(source='unidade_demandante.sigla', read_only=True)
    autoridade_nome = serializers.CharField(source='autoridade.nome', read_only=True)

    class Meta:
        model = ProtocoloEntrega
        fields = [
            'id', 'numero', 'tipo_entrega', 'status_recebimento',
            'vestigio_id', 'vestigio_lacre', 'vestigio_status',
            'ocorrencia_numero',
            'recebido_por_nome', 'unidade_nome', 'unidade_sigla', 'autoridade_nome',
            'entregue_em', 'recebido_em', 'vestigio_foi_finalizado',
        ]


class ProtocoloDetailSerializer(serializers.ModelSerializer):
    vestigio = serializers.SerializerMethodField()
    ocorrencia = serializers.SerializerMethodField()
    procedimento = serializers.SerializerMethodField()
    autoridade = serializers.SerializerMethodField()
    unidade_demandante = serializers.SerializerMethodField()
    entregue_por_obj = serializers.SerializerMethodField()
    recebido_por_usuario_obj = serializers.SerializerMethodField()

    class Meta:
        model = ProtocoloEntrega
        fields = [
            'id', 'numero', 'tipo_entrega',
            'vestigio', 'lacre_na_entrega', 'descricao_material',
            'ocorrencia', 'procedimento',
            'autoridade', 'unidade_demandante',
            'entregue_por_nome', 'entregue_por_cargo', 'entregue_por_cpf', 'entregue_em',
            'entregue_por_obj',
            'recebido_por_nome', 'recebido_por_cargo', 'recebido_por_cpf',
            'recebido_por_matricula', 'recebido_por_usuario_obj', 'recebido_em',
            'status_recebimento', 'protocolo_hash',
            'vestigio_foi_finalizado', 'observacoes',
            'created_at', 'updated_at', 'created_by_id',
        ]

    def get_vestigio(self, obj):
        v = obj.vestigio
        return {
            'id': v.id,
            'lacre': v.lacre,
            'num_processo_sei': v.num_processo_sei,
            'status': v.status,
            'ocorrencia': v.ocorrencia,
            'ano_ocorrencia': v.ano_ocorrencia,
        }

    def get_ocorrencia(self, obj):
        if not obj.ocorrencia:
            return None
        oc = obj.ocorrencia
        return {'id': oc.id, 'numero_ocorrencia': oc.numero_ocorrencia}

    def get_procedimento(self, obj):
        if not obj.procedimento:
            return None
        p = obj.procedimento
        return {'id': p.id, 'descricao': str(p)}

    def get_autoridade(self, obj):
        a = obj.autoridade
        return {
            'id': a.id,
            'nome': a.nome,
            'cargo_nome': a.cargo.nome if a.cargo else None,
        }

    def get_unidade_demandante(self, obj):
        u = obj.unidade_demandante
        return {'id': u.id, 'nome': u.nome, 'sigla': getattr(u, 'sigla', '')}

    def get_entregue_por_obj(self, obj):
        u = obj.entregue_por
        return {'id': u.id, 'nome_completo': u.nome_completo, 'email': u.email, 'perfil': u.perfil}

    def get_recebido_por_usuario_obj(self, obj):
        if not obj.recebido_por_usuario:
            return None
        u = obj.recebido_por_usuario
        return {'id': u.id, 'nome_completo': u.nome_completo, 'email': u.email, 'perfil': u.perfil}


# ─── Serializer de criação ─────────────────────────────────────────────────────

class ProtocoloCreateSerializer(serializers.Serializer):
    vestigio_id = serializers.IntegerField()
    tipo_entrega = serializers.ChoiceField(
        choices=ProtocoloEntrega.TipoEntrega.choices,
        default=ProtocoloEntrega.TipoEntrega.MATERIAL,
    )
    lacre_na_entrega = serializers.CharField(required=False, allow_blank=True, default='')
    descricao_material = serializers.CharField()

    ocorrencia_id = serializers.IntegerField()
    procedimento_id = serializers.IntegerField(required=False, allow_null=True)

    autoridade_id = serializers.IntegerField()
    unidade_demandante_id = serializers.IntegerField()

    recebido_por_nome = serializers.CharField()
    recebido_por_cargo = serializers.CharField()
    recebido_por_cpf = serializers.CharField(required=False, allow_blank=True, default='')
    recebido_por_matricula = serializers.CharField(required=False, allow_blank=True, default='')
    recebido_por_usuario_id = serializers.IntegerField(required=False, allow_null=True)

    observacoes = serializers.CharField(required=False, allow_blank=True, default='')

    # Campos de assinatura — obrigatórios apenas quando o vestígio NÃO está finalizado
    assinatura_email = serializers.EmailField(required=False)
    assinatura_senha = serializers.CharField(required=False, write_only=True)
    motivo_finalizacao = serializers.CharField(required=False, default='Devolução de material via Protocolo de Saída')


class AssinarProtocoloSerializer(serializers.Serializer):
    assinatura_email = serializers.EmailField()
    assinatura_senha = serializers.CharField(write_only=True)
