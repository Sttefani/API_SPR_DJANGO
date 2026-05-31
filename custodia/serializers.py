# custodia/serializers.py

from rest_framework import serializers
from .models import Vestigio, VestigioMovimentacao, DNA
from procedimentos_cadastrados.models import ProcedimentoCadastrado
from autoridades.models import Autoridade
from unidades_demandantes.models import UnidadeDemandante
from servicos_periciais.models import ServicoPericial
from usuarios.models import User


# ---------------------------------------------------------------------------
# Serializers auxiliares (leitura resumida)
# ---------------------------------------------------------------------------

class AutoridadeResumoSerializer(serializers.ModelSerializer):
    cargo_nome = serializers.CharField(source='cargo.nome', read_only=True)

    class Meta:
        from autoridades.models import Autoridade
        model = Autoridade
        fields = ['id', 'nome', 'cargo_nome']


class UnidadeResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadeDemandante
        fields = ['id', 'sigla', 'nome']


class ServicoResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicoPericial
        fields = ['id', 'sigla', 'nome']


class UsuarioResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nome_completo', 'email']


class ProcedimentoCadastradoResumoSerializer(serializers.ModelSerializer):
    numero_completo = serializers.SerializerMethodField()

    class Meta:
        model = ProcedimentoCadastrado
        fields = ['id', 'numero', 'ano', 'numero_completo']

    def get_numero_completo(self, obj):
        return f"{obj.tipo_procedimento.sigla} - {obj.numero}/{obj.ano}"


# ---------------------------------------------------------------------------
# Vestígio
# ---------------------------------------------------------------------------

class VestigioListSerializer(serializers.ModelSerializer):
    unidade_demandante = UnidadeResumoSerializer(read_only=True)
    servico_pericial   = ServicoResumoSerializer(read_only=True)
    autoridade_nome    = serializers.CharField(source='autoridade.nome', read_only=True)
    status_display     = serializers.CharField(source='get_status_display', read_only=True)
    # Usa get_responsavel() — retorna created_by.nome_completo ou responsavel_nome
    criado_por         = serializers.SerializerMethodField()

    def get_criado_por(self, obj):
        return obj.get_responsavel()

    class Meta:
        model = Vestigio
        fields = [
            'id', 'lacre', 'num_processo_sei', 'ocorrencia', 'ano_ocorrencia',
            'status', 'status_display', 'conformidade', 'biologico',
            'saiu_da_custodia', 'unidade_demandante', 'servico_pericial',
            'autoridade_nome', 'criado_por', 'created_at',
        ]


class VestigioDetailSerializer(serializers.ModelSerializer):
    unidade_demandante = UnidadeResumoSerializer(read_only=True)
    servico_pericial   = ServicoResumoSerializer(read_only=True)
    autoridade         = AutoridadeResumoSerializer(read_only=True)
    user_destino       = UsuarioResumoSerializer(read_only=True)
    created_by         = UsuarioResumoSerializer(read_only=True)
    updated_by         = UsuarioResumoSerializer(read_only=True)
    procedimentos      = ProcedimentoCadastradoResumoSerializer(many=True, read_only=True)
    vestigio_contra_prova_lacre = serializers.CharField(
        source='vestigio_contra_prova.lacre', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # Campo calculado para auditoria: prioriza created_by, cai para responsavel_nome (ETL)
    registrado_por = serializers.SerializerMethodField()
    atualizado_por = serializers.SerializerMethodField()

    def get_registrado_por(self, obj):
        return obj.get_responsavel()

    def get_atualizado_por(self, obj):
        if obj.updated_by:
            return obj.updated_by.nome_completo
        return None

    class Meta:
        model = Vestigio
        fields = [
            'id', 'lacre', 'num_processo_sei', 'conformidade', 'biologico',
            'ocorrencia', 'ano_ocorrencia', 'status', 'status_display',
            'descricao', 'saiu_da_custodia',
            'unidade_demandante', 'servico_pericial', 'autoridade',
            'user_destino', 'procedimentos', 'vestigio_contra_prova',
            'vestigio_contra_prova_lacre', 'created_by', 'updated_by',
            'registrado_por', 'atualizado_por',
            'created_at', 'updated_at',
        ]


class VestigioCreateSerializer(serializers.ModelSerializer):
    unidade_demandante_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadeDemandante.objects.all(),
        source='unidade_demandante',
    )
    servico_pericial_id = serializers.PrimaryKeyRelatedField(
        queryset=ServicoPericial.objects.all(),
        source='servico_pericial',
    )
    autoridade_id = serializers.PrimaryKeyRelatedField(
        queryset=Autoridade.objects.all(),
        source='autoridade',
        required=False,
        allow_null=True,
    )
    user_destino_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user_destino',
        required=False,
        allow_null=True,
    )
    vestigio_contra_prova_id = serializers.PrimaryKeyRelatedField(
        queryset=Vestigio.objects.all(),
        source='vestigio_contra_prova',
        required=False,
        allow_null=True,
    )
    procedimentos_ids = serializers.PrimaryKeyRelatedField(
        queryset=ProcedimentoCadastrado.objects.all(),
        source='procedimentos',
        many=True,
        required=False,
    )

    class Meta:
        model = Vestigio
        fields = [
            'lacre', 'num_processo_sei', 'conformidade', 'biologico',
            'ocorrencia', 'ano_ocorrencia', 'descricao',
            'unidade_demandante_id', 'servico_pericial_id', 'autoridade_id',
            'user_destino_id', 'vestigio_contra_prova_id', 'procedimentos_ids',
        ]

    def create(self, validated_data):
        procedimentos = validated_data.pop('procedimentos', [])
        vestigio = Vestigio.objects.create(**validated_data)
        if procedimentos:
            vestigio.procedimentos.set(procedimentos)
        return vestigio

    def update(self, instance, validated_data):
        procedimentos = validated_data.pop('procedimentos', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if procedimentos is not None:
            instance.procedimentos.set(procedimentos)
        return instance


class FinalizarVestigioSerializer(serializers.Serializer):
    saiu_da_custodia = serializers.BooleanField()
    descricao = serializers.CharField(required=False, allow_blank=True)


# ---------------------------------------------------------------------------
# Movimentação de Vestígio
# ---------------------------------------------------------------------------

class VestigioMovimentacaoListSerializer(serializers.ModelSerializer):
    unidade_demandante = UnidadeResumoSerializer(read_only=True)
    servico_pericial   = ServicoResumoSerializer(read_only=True)
    autoridade_nome    = serializers.CharField(source='autoridade.nome', read_only=True)
    user_destino       = UsuarioResumoSerializer(read_only=True)
    # Usa get_responsavel() — prioriza created_by, cai para responsavel_nome (ETL)
    criado_por         = serializers.SerializerMethodField()

    def get_criado_por(self, obj):
        return obj.get_responsavel()

    class Meta:
        model = VestigioMovimentacao
        fields = [
            'id', 'vestigio', 'lacre', 'num_processo_sei', 'descricao',
            'aceito', 'data_hora_aceito',
            'unidade_demandante', 'servico_pericial', 'autoridade_nome',
            'user_destino', 'criado_por', 'created_at',
        ]


class VestigioMovimentacaoCreateSerializer(serializers.ModelSerializer):
    vestigio_id = serializers.PrimaryKeyRelatedField(
        queryset=Vestigio.objects.all(),
        source='vestigio',
    )
    unidade_demandante_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadeDemandante.objects.all(),
        source='unidade_demandante',
        required=False,
        allow_null=True,
    )
    servico_pericial_id = serializers.PrimaryKeyRelatedField(
        queryset=ServicoPericial.objects.all(),
        source='servico_pericial',
        required=False,
        allow_null=True,
    )
    autoridade_id = serializers.PrimaryKeyRelatedField(
        queryset=Autoridade.objects.all(),
        source='autoridade',
        required=False,
        allow_null=True,
    )
    user_destino_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user_destino',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = VestigioMovimentacao
        fields = [
            'vestigio_id', 'lacre', 'num_processo_sei', 'descricao',
            'unidade_demandante_id', 'servico_pericial_id',
            'autoridade_id', 'user_destino_id',
        ]


class AceitarMovimentacaoSerializer(serializers.Serializer):
    """Serializer para o custodiante aceitar uma movimentação recebida."""
    pass  # sem campos extras — o aceite é uma ação simples


# ---------------------------------------------------------------------------
# DNA
# ---------------------------------------------------------------------------

class DNAListSerializer(serializers.ModelSerializer):
    perito_nome               = serializers.CharField(source='perito.nome_completo', read_only=True)
    vestigio_lacre            = serializers.CharField(source='vestigio.lacre', read_only=True)
    finalidade_coleta_display = serializers.CharField(source='get_finalidade_coleta_display', read_only=True)
    situacao_display          = serializers.CharField(source='get_situacao_display', read_only=True)
    foto_url                  = serializers.SerializerMethodField()

    def get_foto_url(self, obj):
        if obj.foto:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.foto.url) if request else obj.foto.url
        return None

    class Meta:
        model = DNA
        fields = [
            'id', 'nome', 'cpf', 'nascimento', 'naturalidade', 'uf',
            'finalidade_coleta', 'finalidade_coleta_display',
            'situacao', 'situacao_display',
            'data_da_coleta', 'codigo_barras', 'foto_url',
            'perito_nome', 'vestigio_lacre', 'created_at',
        ]


class DNADetailSerializer(serializers.ModelSerializer):
    perito     = UsuarioResumoSerializer(read_only=True)
    vestigio   = VestigioListSerializer(read_only=True)
    created_by = UsuarioResumoSerializer(read_only=True)
    finalidade_coleta_display = serializers.CharField(source='get_finalidade_coleta_display', read_only=True)
    situacao_display          = serializers.CharField(source='get_situacao_display', read_only=True)
    gemeo_display             = serializers.CharField(source='get_gemeo_display', read_only=True)
    transfusao_display        = serializers.CharField(source='get_transfusao_display', read_only=True)
    transplante_display       = serializers.CharField(source='get_transplante_display', read_only=True)
    # URL absoluta da foto para exibição
    foto_url = serializers.SerializerMethodField()

    def get_foto_url(self, obj):
        if obj.foto:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.foto.url) if request else obj.foto.url
        return None

    class Meta:
        model = DNA
        fields = '__all__'


class DNACreateSerializer(serializers.ModelSerializer):
    perito_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='perito',
        required=False,
        allow_null=True,
    )
    vestigio_id = serializers.PrimaryKeyRelatedField(
        queryset=Vestigio.objects.all(),
        source='vestigio',
        required=False,
        allow_null=True,
    )
    # Campo de upload — ImageField aceita arquivo via multipart/form-data
    foto = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = DNA
        exclude = ['perito', 'vestigio', 'created_by', 'updated_by', 'deleted_by', 'deleted_at']
        extra_kwargs = {
            'processado_banco_perfis_genetico': {'required': False},
            'nome_foto': {'required': False},
        }
