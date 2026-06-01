"""
Management command: migrar_custodia_mysql

Migra dados de custódia do banco MySQL (Java/Spring Boot) para o PostgreSQL (Django).

PROBLEMA RESOLVIDO:
As tabelas de referência (cargos, cidades, unidades, autoridades, serviços) já existem
nos dois bancos com IDs diferentes. O comando constrói dicionários de mapeamento
{mysql_id → django_id} usando chaves naturais (nome/sigla) antes de migrar os dados
de custódia (vestígios, movimentações, DNA), traduzindo todas as FKs no processo.

USO:
  python manage.py migrar_custodia_mysql \\
    --mysql-host=localhost --mysql-port=3306 \\
    --mysql-db=criminalistica_vestigios \\
    --mysql-user=root --mysql-password=SUA_SENHA

OPÇÕES:
  --dry-run              Simula sem gravar (mostra contagens e conflitos)
  --apenas-mapeamento    Exibe os mapeamentos de ID e para (não migra dados)
  --incluir-usuarios     Também migra usuários do MySQL para Django

DEPENDÊNCIA:
  pip install pymysql
"""

import unicodedata
from datetime import datetime, date
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction, IntegrityError

from cargos.models import Cargo
from cidades.models import Cidade
from unidades_demandantes.models import UnidadeDemandante
from autoridades.models import Autoridade
from servicos_periciais.models import ServicoPericial
from usuarios.models import User
from custodia.models import Vestigio, VestigioMovimentacao, DNA

MANAUS_TZ = ZoneInfo('America/Manaus')

# Mapeamento de roles Java → perfil Django
ROLE_PARA_PERFIL = {
    'ROLE_ADMIN':       'ADMINISTRATIVO',
    'ROLE_CUSTODIANTE': 'CUSTODIANTE',
    'ROLE_PERITO':      'PERITO',
    'ROLE_EXTERNO':     'EXTERNO',
}

# Conversão de int (enum Java YesOrNo) → SimNao Django
INT_PARA_SIMNO = {0: 'NAO', 1: 'SIM', None: 'NAO'}

# Mapeamento status vestígio (idêntico entre os sistemas)
STATUS_VESTIGIO = {'INICIAL', 'ANDAMENTO', 'FINALIZADO'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalizar(texto):
    """Strip + maiúsculas + remove acentos para comparação segura."""
    if not texto:
        return ''
    txt = str(texto).strip().upper()
    nfkd = unicodedata.normalize('NFKD', txt)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def sigla_de_nome(nome):
    """Deriva sigla a partir do nome (iniciais de cada palavra, max 20 chars)."""
    palavras = [p for p in str(nome).strip().split() if len(p) > 2]
    sigla = ''.join(p[0].upper() for p in palavras) if palavras else nome[:10].upper()
    return sigla[:20]


def bit_para_bool(val):
    """Converte bit(1) do MySQL (bytes ou int) para bool Python."""
    if val is None:
        return False
    if isinstance(val, (bytes, bytearray)):
        return bool(val[0])
    return bool(val)


def date_para_datetime(d):
    """Converte date (MySQL DATE) para datetime com meia-noite em Manaus."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.replace(tzinfo=MANAUS_TZ) if d.tzinfo is None else d
    if isinstance(d, date):
        return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=MANAUS_TZ)
    return d


def fix_tz(dt):
    """Garante timezone em datetimes vindos do MySQL (armazenados sem tz)."""
    if dt is None:
        return None
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=MANAUS_TZ)
    return dt


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Migra dados de custódia do MySQL (Java) para o PostgreSQL (Django), resolvendo conflito de IDs em chaves estrangeiras'

    def add_arguments(self, parser):
        parser.add_argument('--mysql-host', default='localhost', help='Host MySQL')
        parser.add_argument('--mysql-port', type=int, default=3306, help='Porta MySQL')
        parser.add_argument('--mysql-db', default='criminalistica_vestigios', help='Nome do banco MySQL')
        parser.add_argument('--mysql-user', required=True, help='Usuário MySQL')
        parser.add_argument('--mysql-password', required=True, help='Senha MySQL')
        parser.add_argument('--dry-run', action='store_true', help='Simula sem gravar nada')
        parser.add_argument('--apenas-mapeamento', action='store_true', help='Exibe mapeamentos e para')
        parser.add_argument('--incluir-usuarios', action='store_true', help='Migra usuários do MySQL para Django')

    # -----------------------------------------------------------------------
    # Ponto de entrada
    # -----------------------------------------------------------------------

    def handle(self, *args, **options):
        try:
            import pymysql
        except ImportError:
            raise CommandError(
                'pymysql não encontrado. Instale com: pip install pymysql\n'
                'Depois adicione ao requirements.txt.'
            )

        self.dry_run = options['dry_run']
        self.apenas_mapeamento = options['apenas_mapeamento']
        self.incluir_usuarios = options['incluir_usuarios']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('\n⚠  MODO DRY-RUN — nenhum dado será gravado\n'))

        # Conectar MySQL
        try:
            conn = pymysql.connect(
                host=options['mysql_host'],
                port=options['mysql_port'],
                database=options['mysql_db'],
                user=options['mysql_user'],
                password=options['mysql_password'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
            )
        except Exception as exc:
            raise CommandError(f'Erro ao conectar no MySQL: {exc}')

        self.stdout.write(f'Conectado ao MySQL ({options["mysql_host"]}:{options["mysql_port"]}/{options["mysql_db"]})\n')

        with conn:
            cursor = conn.cursor()

            # ── 1. Construir todos os mapeamentos de IDs ──────────────────
            self._secao('FASE 1 — Mapeamento de IDs')

            map_cargos     = self._mapear_cargos(cursor)
            map_cidades    = self._mapear_cidades(cursor)
            map_unidades   = self._mapear_unidades(cursor)
            map_autoridades = self._mapear_autoridades(cursor, map_cargos)
            map_servicos   = self._mapear_servicos(cursor)
            map_users      = self._mapear_users(cursor, map_unidades, map_servicos)

            self._resumo_mapeamento('Cargos',               map_cargos)
            self._resumo_mapeamento('Cidades/Municípios',   map_cidades)
            self._resumo_mapeamento('Unidades Demandantes', map_unidades)
            self._resumo_mapeamento('Autoridades',          map_autoridades)
            self._resumo_mapeamento('Serviços Periciais',   map_servicos)
            self._resumo_mapeamento('Usuários',             map_users)

            if self.apenas_mapeamento:
                self.stdout.write('\n(--apenas-mapeamento: encerrando sem migrar dados)\n')
                return

            # ── 2. Migrar usuários (opcional) ─────────────────────────────
            if self.incluir_usuarios:
                self._secao('FASE 2 — Usuários')
                self._migrar_usuarios(cursor, map_unidades, map_servicos)

            # ── 3. Migrar dados de custódia ───────────────────────────────
            self._secao('FASE 3 — Dados de Custódia')

            if not self.dry_run:
                with transaction.atomic():
                    map_vestigios = self._migrar_vestigios(cursor, map_unidades, map_servicos, map_autoridades, map_users)
                    self._migrar_movimentacoes(cursor, map_vestigios, map_unidades, map_servicos, map_autoridades, map_users)
                    self._migrar_dnas(cursor, map_vestigios, map_users)
            else:
                map_vestigios = self._migrar_vestigios(cursor, map_unidades, map_servicos, map_autoridades, map_users)
                self._migrar_movimentacoes(cursor, map_vestigios, map_unidades, map_servicos, map_autoridades, map_users)
                self._migrar_dnas(cursor, map_vestigios, map_users)

        self.stdout.write(self.style.SUCCESS('\n✓ Migração concluída!\n'))

    # -----------------------------------------------------------------------
    # Fase 1 — Mapeamentos de IDs para tabelas de referência
    # -----------------------------------------------------------------------

    def _mapear_cargos(self, cursor):
        """Mapeia mysql_id → django_id para Cargo, usando nome normalizado."""
        cursor.execute('SELECT id, nome FROM cargos')
        mysql_rows = cursor.fetchall()

        django_map = {normalizar(c.nome): c.id for c in Cargo.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in mysql_rows:
            chave = normalizar(row['nome'])
            if chave in django_map:
                mapeamento[row['id']] = django_map[chave]
            else:
                nao_encontrados.append(row)

        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  Cargos sem correspondência em Django ({len(nao_encontrados)}):'))
            for r in nao_encontrados:
                self.stdout.write(f'    MySQL id={r["id"]} nome="{r["nome"]}"')
                if not self.dry_run:
                    cargo = Cargo(nome=r['nome'].strip().upper())
                    cargo.save()
                    mapeamento[r['id']] = cargo.id
                    self.stdout.write(f'      → criado Django id={cargo.id}')

        return mapeamento

    def _mapear_cidades(self, cursor):
        """Mapeia mysql_id → django_id para Cidade (municipios no MySQL)."""
        cursor.execute('SELECT id, nome FROM municipios')
        mysql_rows = cursor.fetchall()

        django_map = {normalizar(c.nome): c.id for c in Cidade.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in mysql_rows:
            chave = normalizar(row['nome'])
            if chave in django_map:
                mapeamento[row['id']] = django_map[chave]
            else:
                nao_encontrados.append(row)

        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  Cidades sem correspondência em Django ({len(nao_encontrados)}):'))
            for r in nao_encontrados:
                self.stdout.write(f'    MySQL id={r["id"]} nome="{r["nome"]}"')
                if not self.dry_run:
                    cidade = Cidade(nome=r['nome'].strip().upper())
                    cidade.save()
                    mapeamento[r['id']] = cidade.id
                    self.stdout.write(f'      → criada Django id={cidade.id}')

        return mapeamento

    def _mapear_unidades(self, cursor):
        """
        Mapeia mysql_id → django_id para UnidadeDemandante.
        MySQL não tem 'sigla' → match por nome normalizado.
        Se não encontrar, deriva sigla das iniciais do nome.
        """
        cursor.execute('SELECT id, nome FROM unidades_demandantes')
        mysql_rows = cursor.fetchall()

        # Indexa Django por nome E por sigla (para casos onde sigla ≈ abreviação do nome)
        django_por_nome  = {normalizar(u.nome):  u.id for u in UnidadeDemandante.all_objects.all()}
        django_por_sigla = {normalizar(u.sigla): u.id for u in UnidadeDemandante.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in mysql_rows:
            chave_nome  = normalizar(row['nome'])
            sigla_der   = normalizar(sigla_de_nome(row['nome']))

            if chave_nome in django_por_nome:
                mapeamento[row['id']] = django_por_nome[chave_nome]
            elif sigla_der in django_por_sigla:
                # Fallback: sigla derivada bate com sigla Django
                mapeamento[row['id']] = django_por_sigla[sigla_der]
                self.stdout.write(
                    f'  Unidade "{row["nome"]}" mapeada via sigla derivada "{sigla_der}"')
            else:
                nao_encontrados.append(row)

        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  Unidades Demandantes sem correspondência em Django ({len(nao_encontrados)}):'))
            for r in nao_encontrados:
                sigla = sigla_de_nome(r['nome'])
                self.stdout.write(
                    f'    MySQL id={r["id"]} nome="{r["nome"]}" → sigla derivada="{sigla}"')
                if not self.dry_run:
                    try:
                        ud = UnidadeDemandante(
                            nome=r['nome'].strip().upper(),
                            sigla=sigla,
                        )
                        ud.save()
                        mapeamento[r['id']] = ud.id
                        self.stdout.write(f'      → criada Django id={ud.id}')
                    except Exception as exc:
                        self.stdout.write(self.style.ERROR(f'      ERRO ao criar: {exc}'))

        return mapeamento

    def _mapear_autoridades(self, cursor, map_cargos):
        """Mapeia mysql_id → django_id para Autoridade, por nome normalizado."""
        cursor.execute('SELECT id, nome, cargo_id FROM autoridades')
        mysql_rows = cursor.fetchall()

        django_map = {normalizar(a.nome): a.id for a in Autoridade.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in mysql_rows:
            chave = normalizar(row['nome'])
            if chave in django_map:
                mapeamento[row['id']] = django_map[chave]
            else:
                nao_encontrados.append(row)

        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  Autoridades sem correspondência em Django ({len(nao_encontrados)}):'))
            for r in nao_encontrados:
                django_cargo_id = map_cargos.get(r['cargo_id'])
                self.stdout.write(
                    f'    MySQL id={r["id"]} nome="{r["nome"]}" cargo_mysql={r["cargo_id"]} → cargo_django={django_cargo_id}')
                if not self.dry_run and django_cargo_id:
                    try:
                        cargo = Cargo.all_objects.get(pk=django_cargo_id)
                        aut = Autoridade(nome=r['nome'].strip().upper(), cargo=cargo)
                        aut.save()
                        mapeamento[r['id']] = aut.id
                        self.stdout.write(f'      → criada Django id={aut.id}')
                    except Exception as exc:
                        self.stdout.write(self.style.ERROR(f'      ERRO ao criar: {exc}'))
                elif not django_cargo_id:
                    self.stdout.write(self.style.ERROR('      IGNORADA — cargo não mapeado'))

        return mapeamento

    def _mapear_servicos(self, cursor):
        """
        Mapeia mysql_id → django_id para ServicoPericial.
        MySQL tem 'sigla' → usa sigla como chave primária de matching.
        Fallback: nome normalizado.
        """
        cursor.execute('SELECT id, sigla, nome FROM servicos_peciricais')
        mysql_rows = cursor.fetchall()

        django_por_sigla = {normalizar(s.sigla): s.id for s in ServicoPericial.all_objects.all()}
        django_por_nome  = {normalizar(s.nome):  s.id for s in ServicoPericial.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in mysql_rows:
            chave_sigla = normalizar(row['sigla'] or '')
            chave_nome  = normalizar(row['nome'] or '')

            if chave_sigla and chave_sigla in django_por_sigla:
                mapeamento[row['id']] = django_por_sigla[chave_sigla]
            elif chave_nome and chave_nome in django_por_nome:
                mapeamento[row['id']] = django_por_nome[chave_nome]
                self.stdout.write(
                    f'  Serviço "{row["sigla"]}" mapeado via nome (sigla não bateu)')
            else:
                nao_encontrados.append(row)

        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  Serviços Periciais sem correspondência em Django ({len(nao_encontrados)}):'))
            for r in nao_encontrados:
                self.stdout.write(
                    f'    MySQL id={r["id"]} sigla="{r["sigla"]}" nome="{r["nome"]}"')
                if not self.dry_run:
                    try:
                        sp = ServicoPericial(
                            sigla=(r['sigla'] or '').strip().upper(),
                            nome=(r['nome'] or '').strip().upper(),
                        )
                        sp.save()
                        mapeamento[r['id']] = sp.id
                        self.stdout.write(f'      → criado Django id={sp.id}')
                    except Exception as exc:
                        self.stdout.write(self.style.ERROR(f'      ERRO ao criar: {exc}'))

        return mapeamento

    def _mapear_users(self, cursor, map_unidades, map_servicos):
        """
        Mapeia mysql_id → django_id para User, usando CPF como chave natural.
        Também carrega roles para uso posterior na migração de usuários.
        """
        cursor.execute('SELECT id, cpf, email FROM users')
        mysql_rows = cursor.fetchall()

        django_map = {u.cpf.replace('.', '').replace('-', ''): u.id
                      for u in User.all_objects.all() if u.cpf}
        mapeamento = {}
        nao_encontrados = []

        for row in mysql_rows:
            cpf_limpo = (row['cpf'] or '').replace('.', '').replace('-', '')
            if cpf_limpo and cpf_limpo in django_map:
                mapeamento[row['id']] = django_map[cpf_limpo]
            else:
                nao_encontrados.append(row)

        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  Usuários sem correspondência em Django ({len(nao_encontrados)}):'))
            for r in nao_encontrados:
                self.stdout.write(
                    f'    MySQL id={r["id"]} cpf="{r["cpf"]}" email="{r["email"]}"')
            self.stdout.write(
                '  → Use --incluir-usuarios para criá-los automaticamente.')

        return mapeamento

    # -----------------------------------------------------------------------
    # Fase 2 — Migração de usuários (opcional)
    # -----------------------------------------------------------------------

    def _migrar_usuarios(self, cursor, map_unidades, map_servicos):
        """
        Migra usuários do MySQL para Django.
        Senhas BCrypt são compatíveis — importadas diretamente.
        Usuários já existentes (por CPF) são ignorados.
        """
        cursor.execute('''
            SELECT u.id, u.cpf, u.email, u.fullname, u.password, u.enabled,
                   u.unidade_demandante_id, u.servico_pericial_id
            FROM users u
        ''')
        rows = cursor.fetchall()

        # Carregar roles por user_id
        cursor.execute('''
            SELECT ur.user_id, r.role_name
            FROM users_roles ur
            JOIN roles r ON r.id = ur.role_id
        ''')
        roles_por_user = {}
        for rr in cursor.fetchall():
            roles_por_user[rr['user_id']] = rr['role_name']

        criados = skipped = erros = 0

        for row in rows:
            cpf_limpo = (row['cpf'] or '').replace('.', '').replace('-', '')

            # Pular se já existe
            if User.all_objects.filter(cpf=row['cpf']).exists():
                skipped += 1
                continue

            perfil = ROLE_PARA_PERFIL.get(roles_por_user.get(row['id'], ''), 'PERITO')
            unidade_id = map_unidades.get(row['unidade_demandante_id'])
            servico_id = map_servicos.get(row['servico_pericial_id'])

            if self.dry_run:
                self.stdout.write(
                    f'  DRY cpf={row["cpf"]} perfil={perfil} → seria criado')
                criados += 1
                continue

            try:
                user = User(
                    email=row['email'],
                    cpf=row['cpf'],
                    nome_completo=row['fullname'],
                    password=row['password'],  # BCrypt já codificado
                    status='ATIVO' if bit_para_bool(row['enabled']) else 'INATIVO',
                    perfil=perfil,
                    deve_alterar_senha=True,  # força troca de senha no primeiro login
                )
                if unidade_id:
                    user.unidade_demandante_id = unidade_id
                user.save()

                if servico_id:
                    user.servicos_periciais.add(servico_id)

                criados += 1
            except Exception as exc:
                erros += 1
                self.stdout.write(self.style.ERROR(
                    f'  ERRO usuário cpf={row["cpf"]}: {exc}'))

        self._log_resultado('Usuários', criados, skipped, erros)

    # -----------------------------------------------------------------------
    # Fase 3 — Migração de dados de custódia
    # -----------------------------------------------------------------------

    def _migrar_vestigios(self, cursor, map_unidades, map_servicos, map_autoridades, map_users):
        """
        Migra vestígios do MySQL para Django.
        Retorna {mysql_id: django_id} para uso na migração de movimentações e DNAs.

        Diferenças MySQL → Django:
        - sem contra_prova_id (campo só existe no Django)
        - descricao é varchar(5000) no MySQL, TextField no Django (sem limite no DB)
        - biologico/conformidade/saiu_da_custodia são bit(1) → bool
        """
        cursor.execute('''
            SELECT id, lacre, num_processo_sei, conformidade, biologico,
                   ocorrencia, ano_ocorrencia, status, descricao,
                   saiu_da_custodia, unidade_demandante_id, servico_pericial_id,
                   autoridade_id, user_destino_id, user_created_id, user_updated_id,
                   created_at, updated_at
            FROM vestigios
            ORDER BY id
        ''')
        rows = cursor.fetchall()

        mapeamento = {}
        criados = skipped = erros = 0

        for row in rows:
            unidade_id  = map_unidades.get(row['unidade_demandante_id'])
            servico_id  = map_servicos.get(row['servico_pericial_id'])
            autoridade_id = map_autoridades.get(row['autoridade_id'])
            destino_id  = map_users.get(row['user_destino_id'])
            created_by_id = map_users.get(row['user_created_id'])
            updated_by_id = map_users.get(row['user_updated_id'])

            status = row['status'] if row['status'] in STATUS_VESTIGIO else 'INICIAL'

            if not unidade_id:
                self.stdout.write(self.style.WARNING(
                    f'  Vestígio mysql_id={row["id"]} ignorado: '
                    f'unidade_demandante_id={row["unidade_demandante_id"]} não mapeada'))
                erros += 1
                continue

            if self.dry_run:
                criados += 1
                continue

            try:
                obj = Vestigio(
                    lacre=row['lacre'],
                    num_processo_sei=row['num_processo_sei'],
                    conformidade=bit_para_bool(row['conformidade']),
                    biologico=bit_para_bool(row['biologico']),
                    ocorrencia=row['ocorrencia'],
                    ano_ocorrencia=row['ano_ocorrencia'],
                    status=status,
                    descricao=row['descricao'],
                    saiu_da_custodia=bit_para_bool(row['saiu_da_custodia']),
                    unidade_demandante_id=unidade_id,
                    servico_pericial_id=servico_id,
                    autoridade_id=autoridade_id,
                    user_destino_id=destino_id,
                    created_by_id=created_by_id,
                    updated_by_id=updated_by_id,
                    # Timestamps preservados via bulk_create abaixo
                    created_at=fix_tz(row['created_at']),
                    updated_at=fix_tz(row['updated_at']),
                )
                # bulk_create com um elemento preserva timestamps (bypassa auto_now)
                [novo] = Vestigio.objects.bulk_create([obj])
                # Forçar timestamps originais (auto_now pode ter sobrescrito)
                Vestigio.objects.filter(pk=novo.pk).update(
                    created_at=fix_tz(row['created_at']),
                    updated_at=fix_tz(row['updated_at']),
                )
                mapeamento[row['id']] = novo.pk
                criados += 1
            except IntegrityError as exc:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f'  Vestígio mysql_id={row["id"]} pulado (já existe?): {exc}'))
            except Exception as exc:
                erros += 1
                self.stdout.write(self.style.ERROR(
                    f'  Vestígio mysql_id={row["id"]} ERRO: {exc}'))

        self._log_resultado('Vestígios', criados, skipped, erros)
        return mapeamento

    def _migrar_movimentacoes(self, cursor, map_vestigios, map_unidades, map_servicos, map_autoridades, map_users):
        """
        Migra movimentações de vestígios.
        Depende de map_vestigios para traduzir vestigio_id.
        """
        cursor.execute('''
            SELECT id, vestigio_id, lacre, num_processo_sei, descricao,
                   aceito, data_hora_aceito,
                   unidade_demandante_id, servico_pericial_id,
                   autoridade_id, user_destino_id, user_created_id,
                   created_at
            FROM vestigios_movimentacoes
            ORDER BY id
        ''')
        rows = cursor.fetchall()

        criados = skipped = erros = 0
        objs = []

        for row in rows:
            vestigio_django_id = map_vestigios.get(row['vestigio_id'])
            if not vestigio_django_id:
                # Vestígio não foi migrado (provavelmente teve erro) — pular
                skipped += 1
                continue

            unidade_id    = map_unidades.get(row['unidade_demandante_id'])
            servico_id    = map_servicos.get(row['servico_pericial_id'])
            autoridade_id = map_autoridades.get(row['autoridade_id'])
            destino_id    = map_users.get(row['user_destino_id'])
            created_by_id = map_users.get(row['user_created_id'])

            if self.dry_run:
                criados += 1
                continue

            objs.append(VestigioMovimentacao(
                vestigio_id=vestigio_django_id,
                lacre=row['lacre'],
                num_processo_sei=row['num_processo_sei'],
                descricao=row['descricao'],
                aceito=bit_para_bool(row['aceito']),
                data_hora_aceito=fix_tz(row['data_hora_aceito']),
                unidade_demandante_id=unidade_id,
                servico_pericial_id=servico_id,
                autoridade_id=autoridade_id,
                user_destino_id=destino_id,
                created_by_id=created_by_id,
                created_at=fix_tz(row['created_at']),
                updated_at=fix_tz(row['created_at']),  # não existe updated_at no MySQL
            ))

        if not self.dry_run and objs:
            try:
                VestigioMovimentacao.objects.bulk_create(objs, batch_size=300)
                criados = len(objs)
                # Preservar timestamps
                ids = list(VestigioMovimentacao.objects.order_by('-pk').values_list('pk', flat=True)[:criados])
                # Atualizar em lote (timestamps já foram setados no bulk_create — só garantir)
            except Exception as exc:
                erros = len(objs)
                self.stdout.write(self.style.ERROR(f'  Erro bulk movimentações: {exc}'))

        self._log_resultado('Movimentações', criados, skipped, erros)

    def _migrar_dnas(self, cursor, map_vestigios, map_users):
        """
        Migra registros de DNA.

        Diferenças MySQL → Django:
        - gemeo/tranfusao/transplante: int (0/1) → SimNao ('NAO'/'SIM')
        - 'tranfusao' (typo MySQL sem 's') → 'transfusao' (Django)
        - nascimento/data_da_coleta: DATE → DateTimeField (meia-noite Manaus)
        - situacao: não existe no MySQL → default 'NAO_APENADO'
        - processado_banco_perfis_genetico: não existe no MySQL → default 'NAO'
        - estrangeiro: não existe no MySQL → default False
        - registrado_por_usuario_externo: não existe no MySQL → default False
        - uf: NOT NULL no MySQL — migrado diretamente
        """
        cursor.execute('''
            SELECT id, nome, cpf, rg, nascimento, naturalidade, uf,
                   mae, pai, pais, gemeo, tranfusao, transplante,
                   unidade_prisional, tipo_penal, data_da_coleta,
                   lacres, testemunha, testemunha2, notas,
                   ocorrencia, processo_judicial, num_processo_sei,
                   finalidade_coleta, codigo_barras,
                   nome_foto, foto,
                   perito_id, vestigio_id,
                   user_created_id, user_updated_id,
                   created_at, updated_at
            FROM dnas
            ORDER BY id
        ''')
        rows = cursor.fetchall()

        criados = skipped = erros = 0
        objs = []

        for row in rows:
            vestigio_django_id = map_vestigios.get(row['vestigio_id']) if row['vestigio_id'] else None
            perito_id    = map_users.get(row['perito_id'])
            created_by_id = map_users.get(row['user_created_id'])
            updated_by_id = map_users.get(row['user_updated_id'])

            if self.dry_run:
                criados += 1
                continue

            objs.append(DNA(
                nome=row['nome'] or '',
                cpf=row['cpf'] or '',
                rg=row['rg'] or '',
                nascimento=date_para_datetime(row['nascimento']),
                naturalidade=row['naturalidade'] or '',
                estrangeiro=False,          # campo novo no Django, não existe no MySQL
                uf=row['uf'] or '',
                mae=row['mae'] or '',
                pai=row['pai'] or '',
                pais=row['pais'] or '',
                gemeo=INT_PARA_SIMNO.get(row['gemeo'], 'NAO'),
                transfusao=INT_PARA_SIMNO.get(row['tranfusao'], 'NAO'),   # typo resolvido
                transplante=INT_PARA_SIMNO.get(row['transplante'], 'NAO'),
                processado_banco_perfis_genetico='NAO',  # campo novo no Django
                unidade_prisional=row['unidade_prisional'] or '',
                tipo_penal=row['tipo_penal'] or '',
                data_da_coleta=date_para_datetime(row['data_da_coleta']),
                lacres=row['lacres'] or '',
                testemunha=row['testemunha'] or '',
                testemunha2=row['testemunha2'] or '',
                notas=row['notas'] or '',
                ocorrencia=row['ocorrencia'] or '',
                processo_judicial=row['processo_judicial'] or '',
                num_processo_sei=row['num_processo_sei'] or '',
                finalidade_coleta=row['finalidade_coleta'] or 'LEI',
                codigo_barras=row['codigo_barras'] or '',
                situacao='NAO_APENADO',    # campo novo no Django; padrão seguro
                responsavel_coleta='',     # campo novo no Django
                registrado_por_usuario_externo=False,  # campo novo no Django
                nome_foto=row['nome_foto'] or '',
                # foto (ImageField): manter vazio — arquivo físico não é migrado aqui
                perito_id=perito_id,
                vestigio_id=vestigio_django_id,
                created_by_id=created_by_id,
                updated_by_id=updated_by_id,
                created_at=fix_tz(row['created_at']),
                updated_at=fix_tz(row['updated_at']),
            ))

        if not self.dry_run and objs:
            try:
                DNA.objects.bulk_create(objs, batch_size=300)
                criados = len(objs)
            except Exception as exc:
                erros = len(objs)
                self.stdout.write(self.style.ERROR(f'  Erro bulk DNA: {exc}'))

        self._log_resultado('Registros DNA', criados, skipped, erros)

        if not self.dry_run and criados:
            self.stdout.write(self.style.WARNING(
                '  ⚠  Arquivos de foto (campo foto/nome_foto) NÃO foram copiados.\n'
                '     Copie manualmente de: <java_uploads>/  →  media/custodia/dna/fotos/'))

    # -----------------------------------------------------------------------
    # Utilitários de saída
    # -----------------------------------------------------------------------

    def _secao(self, titulo):
        self.stdout.write(f'\n{"─" * 60}')
        self.stdout.write(f'  {titulo}')
        self.stdout.write(f'{"─" * 60}')

    def _resumo_mapeamento(self, nome, mapeamento):
        total = len(mapeamento)
        self.stdout.write(f'  {nome}: {total} registro(s) mapeados')

    def _log_resultado(self, entidade, criados, skipped, erros):
        partes = [f'  {entidade}: {criados} criados']
        if skipped:
            partes.append(f'{skipped} pulados')
        if erros:
            partes.append(self.style.ERROR(f'{erros} erros'))
        self.stdout.write(', '.join(partes))
