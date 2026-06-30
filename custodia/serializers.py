# custodia/serializers.py

from rest_framework import serializers
from .models import Vestigio, VestigioMovimentacao, DNA
from procedimentos_cadastrados.models import ProcedimentoCadastrado
from autoridades.models import Autoridade
from unidades_demandantes.models import UnidadeDemandante
from servicos_periciais.models import ServicoPericial
from usuarios.models import User
from ocorrencias.models import Ocorrencia


# ---------------------------------------------------------------------------
# Serializers auxiliares (leitura resumida)
# ---------------------------------------------------------------------------

class AutoridadeResumoSerializer(serializers.ModelSerializer):
    cargo_nome = serializers.CharField(source='cargo.nome', read_only=True)

    class Meta:
        from autoridades.models import Autoridade
        model = Autoridade
        fields = ['id', 'nome', 'cargo_nome']


class ProcedimentoResumoSerializer(serializers.ModelSerializer):
    tipo_sigla = serializers.CharField(source='tipo_procedimento.sigla', read_only=True)
    tipo_nome  = serializers.CharField(source='tipo_procedimento.nome',  read_only=True)
    numero_completo = serializers.SerializerMethodField()

    def get_numero_completo(self, obj):
        return f"{obj.tipo_procedimento.sigla} {obj.numero}/{obj.ano}"

    class Meta:
        model = ProcedimentoCadastrado
        fields = ['id', 'numero', 'ano', 'tipo_sigla', 'tipo_nome', 'numero_completo']


class OcorrenciaResumoSerializer(serializers.ModelSerializer):
    servico_sigla    = serializers.CharField(source='servico_pericial.sigla', read_only=True)
    unidade_sigla    = serializers.CharField(source='unidade_demandante.sigla', read_only=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    procedimento     = ProcedimentoResumoSerializer(source='procedimento_cadastrado', read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            'id', 'numero_ocorrencia', 'status', 'status_display',
            'servico_sigla', 'unidade_sigla', 'procedimento',
        ]


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
        fields = ['id', 'nome_completo', 'email', 'perfil']


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
    servico_pericial_origem = ServicoResumoSerializer(read_only=True)  # origem imutável (cadastro)
    autoridade         = AutoridadeResumoSerializer(read_only=True)
    user_destino       = UsuarioResumoSerializer(read_only=True)
    created_by         = UsuarioResumoSerializer(read_only=True)
    updated_by         = UsuarioResumoSerializer(read_only=True)
    procedimentos      = ProcedimentoCadastradoResumoSerializer(many=True, read_only=True)
    ocorrencias_vinculadas = OcorrenciaResumoSerializer(many=True, read_only=True)
    vestigio_contra_prova_lacre = serializers.CharField(
        source='vestigio_contra_prova.lacre', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    registrado_por  = serializers.SerializerMethodField()
    registrado_por_servico = serializers.SerializerMethodField()
    atualizado_por  = serializers.SerializerMethodField()
    pode_movimentar = serializers.SerializerMethodField()
    pode_editar     = serializers.SerializerMethodField()
    localizacao_atual = serializers.SerializerMethodField()
    servico_origem_nome     = serializers.SerializerMethodField()
    servico_origem_inferido = serializers.SerializerMethodField()

    def get_registrado_por(self, obj):
        return obj.get_responsavel()

    def get_registrado_por_servico(self, obj):
        """Serviço(s) do registrante (created_by) — '' se indisponível."""
        return obj.servicos_do_registrante()

    def get_servico_origem_nome(self, obj):
        texto, _ = obj.origem_display()
        return texto

    def get_servico_origem_inferido(self, obj):
        _, inferido = obj.origem_display()
        return inferido

    def get_localizacao_atual(self, obj):
        """
        Onde o vestígio está AGORA (dinâmico): destino da última movimentação
        aceita — serviço interno OU unidade externa. Sem movimentação aceita,
        permanece no serviço de cadastro/posse atual. Distinto da origem imutável.
        """
        ultima = (
            VestigioMovimentacao.objects
            .filter(vestigio=obj, aceito=True)
            .select_related('servico_pericial', 'unidade_demandante')
            .order_by('-data_hora_aceito', '-created_at')
            .first()
        )
        if ultima:
            if ultima.servico_pericial_id:
                s = ultima.servico_pericial
                return {'tipo': 'servico', 'sigla': s.sigla, 'nome': s.nome}
            if ultima.unidade_demandante_id:
                u = ultima.unidade_demandante
                return {'tipo': 'unidade', 'sigla': u.sigla, 'nome': u.nome}
        if obj.servico_pericial_id:
            s = obj.servico_pericial
            return {'tipo': 'servico', 'sigla': s.sigla, 'nome': s.nome}
        return None

    def get_atualizado_por(self, obj):
        if obj.updated_by:
            return obj.updated_by.nome_completo
        return None

    def get_pode_editar(self, obj):
        """
        Editável apenas: (1) não finalizado, (2) sem nenhuma movimentação (cadeia
        de custódia imutável a partir do 1º movimento) e (3) pelo usuário lotado no
        serviço pericial de cadastro (ou SUPER_ADMIN). Espelha o perform_update.
        """
        if obj.status == 'FINALIZADO':
            return False
        if VestigioMovimentacao.objects.filter(vestigio=obj).exists():
            return False
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.pode_editar_por_lotacao(request.user)

    def get_pode_movimentar(self, obj):
        """
        True se o usuário atual pode registrar nova movimentação neste vestígio.
        Replica a lógica combinada de _pode_ter_nova_movimentacao +
        _posso_realizar_movimentacao do VestigioMovimentacaoViewSet.
        """
        if obj.status == 'FINALIZADO':
            return False
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        user = request.user

        ultima = VestigioMovimentacao.objects.filter(
            vestigio=obj
        ).order_by('-created_at').first()

        # Bloqueia se há movimentação pendente
        if ultima is not None and not ultima.aceito:
            return False

        # EXTERNO: pode movimentar APENAS na primeira transferência (envio à custódia)
        # — ou seja, criou o vestígio e ainda não há movimentação alguma
        if user.perfil == 'EXTERNO':
            return ultima is None and obj.created_by_id == user.pk

        # Admin sempre podem (quando não há pendente)
        if getattr(user, 'is_superuser', False) or user.perfil in {'ADMINISTRATIVO', 'SUPER_ADMIN'}:
            return True

        # Primeira movimentação ou CUSTODIANTE: qualquer perfil autorizado pode
        if ultima is None or user.perfil == 'CUSTODIANTE':
            return True

        # Após aceite: apenas user_destino ou quem está no serviço de destino
        if ultima.user_destino_id == user.pk:
            return True
        if ultima.servico_pericial_id:
            return user.servicos_periciais.filter(id=ultima.servico_pericial_id).exists()

        return False

    class Meta:
        model = Vestigio
        fields = [
            'id', 'lacre', 'num_processo_sei', 'conformidade', 'biologico',
            'ocorrencia', 'ano_ocorrencia', 'status', 'status_display',
            'descricao', 'saiu_da_custodia', 'motivo_finalizacao',
            'unidade_demandante', 'servico_pericial', 'servico_pericial_origem',
            'servico_origem_nome', 'servico_origem_inferido',
            'localizacao_atual', 'autoridade',
            'user_destino', 'procedimentos', 'ocorrencias_vinculadas',
            'vestigio_contra_prova', 'vestigio_contra_prova_lacre',
            'created_by', 'updated_by', 'registrado_por', 'registrado_por_servico',
            'atualizado_por', 'created_at', 'updated_at', 'pode_movimentar', 'pode_editar',
        ]


class VestigioCreateSerializer(serializers.ModelSerializer):
    # Usamos all_objects (inclui soft-deleted) para replicar o comportamento do
    # Java (findById ignora deleção lógica). Assim edições de vestígios que
    # referenciam objetos arquivados não falham com "Pk inválido".
    unidade_demandante_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadeDemandante.all_objects.all(),
        source='unidade_demandante',
    )
    servico_pericial_id = serializers.PrimaryKeyRelatedField(
        queryset=ServicoPericial.all_objects.all(),
        source='servico_pericial',
    )
    autoridade_id = serializers.PrimaryKeyRelatedField(
        queryset=Autoridade.all_objects.all(),
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
        queryset=Vestigio.all_objects.all(),
        source='vestigio_contra_prova',
        required=False,
        allow_null=True,
    )
    procedimentos_ids = serializers.PrimaryKeyRelatedField(
        queryset=ProcedimentoCadastrado.all_objects.all(),
        source='procedimentos',
        many=True,
        required=False,
    )
    # Permite vincular ocorrências já no momento do cadastro.
    # O create() aplica a cascata: se a ocorrência tiver procedimento,
    # este também é adicionado a vestigio.procedimentos.
    ocorrencias_vinculadas_ids = serializers.PrimaryKeyRelatedField(
        queryset=Ocorrencia.objects.all(),
        source='ocorrencias_vinculadas',
        many=True,
        required=False,
    )

    class Meta:
        model = Vestigio
        fields = [
            'id', 'status',
            'lacre', 'num_processo_sei', 'conformidade', 'biologico',
            'ocorrencia', 'ano_ocorrencia', 'descricao',
            'unidade_demandante_id', 'servico_pericial_id', 'autoridade_id',
            'user_destino_id', 'vestigio_contra_prova_id',
            'procedimentos_ids', 'ocorrencias_vinculadas_ids',
        ]
        read_only_fields = ['id', 'status']
        # Regra do administrador: lacre e descrição obrigatórios no cadastro.
        # unidade_demandante_id já é obrigatório (PrimaryKeyRelatedField sem required=False).
        # Enforcement no backend (nunca confiar só no frontend).
        extra_kwargs = {
            'lacre':     {'required': True, 'allow_null': False, 'allow_blank': False},
            'descricao': {'required': True, 'allow_null': False, 'allow_blank': False},
        }

    def validate_lacre(self, value):
        """
        Normaliza o lacre para CAIXA ALTA (sem espaços nas bordas) já na entrada,
        garantindo que a checagem de duplicata abaixo seja case-insensitiva de fato
        e que o valor gravado fique padronizado mesmo via API direta.
        """
        return value.strip().upper() if value else value

    def validate(self, data):
        """
        Duplicidade de vestígio. Com ocorrência/ano removidos do cadastro e o
        lacre agora obrigatório, a chave de unicidade é lacre + servico_pericial
        (redução natural da chave antiga lacre+ocorrência+ano+serviço do Java).
        Em PATCH parcial, recai sobre os valores já gravados quando ausentes.
        """
        lacre   = data.get('lacre')           or (self.instance.lacre           if self.instance else None)
        servico = data.get('servico_pericial') or (self.instance.servico_pericial if self.instance else None)

        if lacre and servico:
            qs = Vestigio.objects.filter(lacre=lacre, servico_pericial=servico)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'detail': 'Já existe um vestígio com esse lacre neste serviço pericial.'}
                )

        return data

    def create(self, validated_data):
        procedimentos    = validated_data.pop('procedimentos', [])
        ocorrencias      = validated_data.pop('ocorrencias_vinculadas', [])
        vestigio = Vestigio.objects.create(**validated_data)

        if procedimentos:
            vestigio.procedimentos.set(procedimentos)

        if ocorrencias:
            vestigio.ocorrencias_vinculadas.set(ocorrencias)
            # Cascata: vincula o procedimento de cada ocorrência ao vestígio
            for oc in ocorrencias:
                oc_com_proc = Ocorrencia.objects.select_related(
                    'procedimento_cadastrado'
                ).filter(pk=oc.pk, procedimento_cadastrado__isnull=False).first()
                if oc_com_proc:
                    vestigio.procedimentos.add(oc_com_proc.procedimento_cadastrado)
            # Auto-preenche ocorrencia/ano_ocorrencia a partir da ocorrência vinculada
            vestigio.sincronizar_ocorrencia_principal()

        return vestigio

    def update(self, instance, validated_data):
        procedimentos = validated_data.pop('procedimentos', None)
        ocorrencias   = validated_data.pop('ocorrencias_vinculadas', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if procedimentos is not None:
            instance.procedimentos.set(procedimentos)
        if ocorrencias is not None:
            instance.ocorrencias_vinculadas.set(ocorrencias)
            for oc in ocorrencias:
                if oc.procedimento_cadastrado:
                    instance.procedimentos.add(oc.procedimento_cadastrado)
            # Mantém ocorrencia/ano_ocorrencia em sincronia com o vínculo
            instance.sincronizar_ocorrencia_principal()
        return instance


class FinalizarVestigioSerializer(serializers.Serializer):
    saiu_da_custodia   = serializers.BooleanField()
    motivo_finalizacao = serializers.CharField(required=True)
    # Campos de assinatura digital — verificados no backend, nunca salvos
    assinatura_email   = serializers.EmailField(write_only=True)
    assinatura_senha   = serializers.CharField(write_only=True)


# ---------------------------------------------------------------------------
# Movimentação de Vestígio
# ---------------------------------------------------------------------------

class VestigioMovimentacaoListSerializer(serializers.ModelSerializer):
    unidade_demandante = UnidadeResumoSerializer(read_only=True)
    servico_pericial   = ServicoResumoSerializer(read_only=True)
    autoridade_nome    = serializers.CharField(source='autoridade.nome', read_only=True)
    user_destino       = UsuarioResumoSerializer(read_only=True)
    # Usa get_responsavel() — prioriza created_by, cai para responsavel_nome (ETL)
    criado_por    = serializers.SerializerMethodField()
    pode_aceitar  = serializers.SerializerMethodField()
    pode_editar   = serializers.SerializerMethodField()
    sou_o_emissor = serializers.SerializerMethodField()
    lacre_efetivo = serializers.SerializerMethodField()
    lacre_mantido = serializers.SerializerMethodField()

    def get_criado_por(self, obj):
        return obj.get_responsavel()

    def get_pode_editar(self, obj):
        """
        Espelha VestigioMovimentacaoViewSet.perform_update: editável apenas
        ANTES do aceite, com vestígio não finalizado, e somente por quem está
        lotado no serviço de ORIGEM (quem enviou o passe) — SUPER_ADMIN break-glass.
        ADMINISTRATIVO NÃO tem override (alinhado à regra de edição de vestígio).
        """
        if obj.aceito:
            return False
        if obj.vestigio_id and obj.vestigio.status == 'FINALIZADO':
            return False
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        # EXTERNO é bloqueado no update pelo PodeCustodiar — não exibir o botão.
        if user.perfil == 'EXTERNO':
            return False
        return obj.pode_editar_por_lotacao(user)

    def get_sou_o_emissor(self, obj):
        """True se o usuário autenticado foi quem criou esta movimentação."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.created_by_id == request.user.pk

    def get_pode_aceitar(self, obj):
        """Replica exata da lógica do action aceitar() — só o destinatário/admin pode aceitar."""
        if obj.aceito:
            return False
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        # Override global: SUPER_ADMIN. ADMINISTRATIVO NÃO — recebe só por lotação.
        if getattr(user, 'is_superuser', False) or user.perfil == 'SUPER_ADMIN':
            return True
        # CUSTODIANTE pode aceitar, mas nunca a sua própria movimentação (ele é o emissor)
        if user.perfil == 'CUSTODIANTE':
            return obj.created_by_id != user.pk
        # PERITO / OPERACIONAL / ADMINISTRATIVO: só se lotado no serviço de destino
        # (lógica Java isMesmoServicoPericial)
        if obj.servico_pericial_id:
            return user.servicos_periciais.filter(id=obj.servico_pericial_id).exists()
        # EXTERNO da mesma unidade demandante
        if user.perfil == 'EXTERNO' and obj.unidade_demandante_id and user.unidade_demandante_id:
            return obj.unidade_demandante_id == user.unidade_demandante_id
        return False

    def _resolver_lacre(self, obj):
        """
        (lacre_efetivo, mantido): o lacre vigente NESTA movimentação. Se a própria
        movimentação informou um novo lacre, é ele (mantido=False). Se não informou,
        herda o lacre mais recente informado ANTES dela; se nenhuma anterior informou,
        herda o lacre inicial do vestígio (mantido=True). Espelha o rastreio de lacre
        da FAV — toda movimentação referencia um lacre, tendo-o alterado ou não.
        """
        cache = getattr(obj, '_lacre_efetivo_cache', None)
        if cache is not None:
            return cache
        if obj.lacre:
            resultado = (obj.lacre, False)
        else:
            anterior = (
                VestigioMovimentacao.objects
                .filter(vestigio_id=obj.vestigio_id, created_at__lt=obj.created_at)
                .exclude(lacre__isnull=True).exclude(lacre='')
                .order_by('-created_at')
                .values_list('lacre', flat=True)
                .first()
            )
            herdado = anterior or (obj.vestigio.lacre if obj.vestigio_id else None)
            resultado = (herdado or None, bool(herdado))
        obj._lacre_efetivo_cache = resultado
        return resultado

    def get_lacre_efetivo(self, obj):
        return self._resolver_lacre(obj)[0]

    def get_lacre_mantido(self, obj):
        return self._resolver_lacre(obj)[1]

    class Meta:
        model = VestigioMovimentacao
        fields = [
            'id', 'vestigio', 'lacre', 'lacre_efetivo', 'lacre_mantido',
            'num_processo_sei', 'descricao',
            'aceito', 'data_hora_aceito',
            'unidade_demandante', 'servico_pericial', 'autoridade_nome',
            'user_destino', 'criado_por', 'created_at', 'pode_aceitar', 'pode_editar', 'sou_o_emissor',
        ]


class VestigioMovimentacaoCreateSerializer(serializers.ModelSerializer):
    vestigio_id = serializers.PrimaryKeyRelatedField(
        queryset=Vestigio.all_objects.all(),
        source='vestigio',
    )
    unidade_demandante_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadeDemandante.all_objects.all(),
        source='unidade_demandante',
        required=False,
        allow_null=True,
    )
    servico_pericial_id = serializers.PrimaryKeyRelatedField(
        queryset=ServicoPericial.all_objects.all(),
        source='servico_pericial',
        required=False,
        allow_null=True,
    )
    autoridade_id = serializers.PrimaryKeyRelatedField(
        queryset=Autoridade.all_objects.all(),
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
            'id',
            'vestigio_id', 'lacre', 'num_processo_sei', 'descricao',
            'unidade_demandante_id', 'servico_pericial_id',
            'autoridade_id', 'user_destino_id',
        ]
        read_only_fields = ['id']


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
    updated_by = UsuarioResumoSerializer(read_only=True)
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
        queryset=Vestigio.all_objects.all(),
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
