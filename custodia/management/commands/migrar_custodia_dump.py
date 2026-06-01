"""
Management command: migrar_custodia_dump

Migra dados de custódia lendo DIRETAMENTE o arquivo SQL do MySQL dump —
sem precisar de MySQL instalado ou rodando.

USO:
  python manage.py migrar_custodia_dump \
    --sql-file "C:/dev/spr-custodia/config servidor/criminalistica_vestigios_2025-05-12_12-00-02.sql"

OPÇÕES:
  --dry-run              Mostra contagens sem gravar nada
  --apenas-mapeamento    Exibe os mapeamentos de ID e para (não migra dados)
  --incluir-usuarios     Também migra usuários do dump para Django
  --sql-file PATH        Caminho para o arquivo .sql (obrigatório)
"""

import re
import unicodedata
from datetime import datetime, date
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError

from cargos.models import Cargo
from cidades.models import Cidade
from unidades_demandantes.models import UnidadeDemandante
from autoridades.models import Autoridade
from servicos_periciais.models import ServicoPericial
from usuarios.models import User
from custodia.models import Vestigio, VestigioMovimentacao, DNA

MANAUS_TZ = ZoneInfo('America/Manaus')

ROLE_PARA_PERFIL = {
    'ROLE_ADMIN':       'ADMINISTRATIVO',
    'ROLE_CUSTODIANTE': 'CUSTODIANTE',
    'ROLE_PERITO':      'PERITO',
    'ROLE_EXTERNO':     'EXTERNO',
}

INT_PARA_SIMNO = {0: 'NAO', 1: 'SIM', None: 'NAO'}
STATUS_VESTIGIO = {'INICIAL', 'ANDAMENTO', 'FINALIZADO'}


# ---------------------------------------------------------------------------
# Helpers de conversão
# ---------------------------------------------------------------------------

def normalizar(texto):
    if not texto:
        return ''
    txt = str(texto).strip().upper()
    nfkd = unicodedata.normalize('NFKD', txt)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def sigla_de_nome(nome):
    palavras = [p for p in str(nome).strip().split() if len(p) > 2]
    sigla = ''.join(p[0].upper() for p in palavras) if palavras else nome[:10].upper()
    return sigla[:20]


def to_bool(val):
    if val is None:
        return False
    if isinstance(val, (bytes, bytearray)):
        return bool(val[0])
    return bool(int(val))


def to_datetime(val):
    """String 'YYYY-MM-DD HH:MM:SS.ffffff' ou date obj -> datetime com tz Manaus."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=MANAUS_TZ) if val.tzinfo is None else val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, 0, 0, 0, tzinfo=MANAUS_TZ)
    if isinstance(val, str):
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(val, fmt)
                return dt.replace(tzinfo=MANAUS_TZ)
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Parser do dump MySQL
# ---------------------------------------------------------------------------

class _Tokenizer:
    """
    Lê a string de VALUES de um INSERT MySQL:
    (v1,v2,NULL,...),(v1,...), ...
    e retorna lista de listas de valores Python.
    """

    def __init__(self, text):
        self.t = text
        self.p = 0
        self.n = len(text)

    def parse(self):
        rows = []
        while self.p < self.n:
            self._ws()
            if self.p >= self.n:
                break
            if self.t[self.p] == '(':
                try:
                    rows.append(self._row())
                except Exception:
                    break
            elif self.t[self.p] == ',':
                self.p += 1
            else:
                break
        return rows

    def _row(self):
        self.p += 1          # pula '('
        vals = []
        while self.p < self.n and self.t[self.p] != ')':
            self._ws()
            if self.p < self.n and self.t[self.p] == ')':
                break
            vals.append(self._val())
            self._ws()
            if self.p < self.n and self.t[self.p] == ',':
                self.p += 1
        if self.p < self.n:
            self.p += 1      # pula ')'
        return vals

    def _val(self):
        if self.p >= self.n:
            return None
        # NULL antes de qualquer outra coisa
        if self.t[self.p:self.p + 4].upper() == 'NULL':
            self.p += 4
            return None
        c = self.t[self.p]
        # bit literal b'0' / b'1'  ->  b'0'=0, b'1'=1
        if c == 'b' and self.p + 1 < self.n and self.t[self.p + 1] == "'":
            self.p += 1
            s = self._str()
            return 0 if (not s or s in ('0', '\x00')) else 1
        # _binary '...' — MySQL 8 exporta bit(1) assim
        # ex.: _binary '' onde entre as aspas está chr(1) invisível
        if c == '_' and self.t[self.p:self.p + 8] == "_binary ":
            self.p += 8  # pula "_binary "
            if self.p < self.n and self.t[self.p] == "'":
                s = self._str()
                return 0 if (not s or s == '\x00') else 1
            return None
        # string
        if c == "'":
            return self._str()
        # número (inclui identificadores como _latin2 que serão ignorados como None)
        return self._num()

    def _str(self):
        self.p += 1          # pula abertura '
        parts = []
        while self.p < self.n:
            c = self.t[self.p]
            if c == '\\':
                self.p += 1
                if self.p < self.n:
                    e = self.t[self.p]
                    parts.append(
                        {'n': '\n', 'r': '\r', 't': '\t', "'": "'",
                         '\\': '\\', '0': '\0', 'Z': '\x1a'}.get(e, e))
                    self.p += 1
            elif c == "'":
                self.p += 1
                if self.p < self.n and self.t[self.p] == "'":  # '' -> '
                    parts.append("'")
                    self.p += 1
                else:
                    break
            else:
                parts.append(c)
                self.p += 1
        return ''.join(parts)

    def _num(self):
        s = self.p
        while self.p < self.n and self.t[self.p] not in (',', ')', ' ', '\t', '\n', '\r'):
            self.p += 1
        raw = self.t[s:self.p].strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            return raw

    def _ws(self):
        while self.p < self.n and self.t[self.p] in (' ', '\t', '\n', '\r'):
            self.p += 1


class MySQLDumpParser:
    """
    Lê um arquivo de dump MySQL e expõe os dados como listas de dicts.

    dump = MySQLDumpParser('/path/to/dump.sql')
    for row in dump.tabela('cargos'):
        print(row['id'], row['nome'])
    """

    def __init__(self, filepath):
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            self._sql = f.read()
        self._colunas: dict[str, list] = {}   # tabela -> [col1, col2, ...]
        self._dados: dict[str, list] = {}     # tabela -> [{col: val, ...}, ...]
        self._processar()

    def _processar(self):
        self._extrair_colunas()
        self._extrair_dados()

    def _extrair_colunas(self):
        """Extrai a ordem das colunas de cada CREATE TABLE."""
        bloco_re = re.compile(
            r'CREATE TABLE `(\w+)` \((.*?)\)\s*ENGINE=',
            re.DOTALL | re.IGNORECASE
        )
        for m in bloco_re.finditer(self._sql):
            tabela = m.group(1)
            definicao = m.group(2)
            colunas = []
            for linha in definicao.splitlines():
                linha = linha.strip()
                if not linha.startswith('`'):
                    continue  # pula PKs, KEYs, CONSTRAINTs
                col_m = re.match(r'`(\w+)`', linha)
                if col_m:
                    colunas.append(col_m.group(1))
            if colunas:
                self._colunas[tabela] = colunas

    def _extrair_dados(self):
        """Extrai linhas de cada INSERT INTO."""
        insert_re = re.compile(
            r"INSERT INTO `(\w+)` VALUES\s+(.*?);",
            re.DOTALL | re.IGNORECASE
        )
        for m in insert_re.finditer(self._sql):
            tabela = m.group(1)
            values_str = m.group(2)
            if tabela not in self._colunas:
                continue
            colunas = self._colunas[tabela]
            linhas_raw = _Tokenizer(values_str).parse()
            linhas = []
            for raw in linhas_raw:
                if len(raw) == len(colunas):
                    linhas.append(dict(zip(colunas, raw)))
                else:
                    # Número de colunas não bateu — reportar mas continuar
                    pass
            if linhas:
                self._dados[tabela] = linhas

    def tabela(self, nome: str) -> list[dict]:
        """Retorna lista de dicts para a tabela, ou [] se não encontrada."""
        return self._dados.get(nome, [])

    def tabelas_disponiveis(self) -> list[str]:
        return sorted(self._dados.keys())


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Migra dados de custódia lendo o arquivo SQL do dump MySQL (sem precisar de MySQL instalado)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-file', required=True,
            help='Caminho para o arquivo .sql do dump MySQL'
        )
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula sem gravar nada')
        parser.add_argument('--apenas-mapeamento', action='store_true',
                            help='Exibe mapeamentos de ID e para')
        parser.add_argument('--incluir-usuarios', action='store_true',
                            help='Migra usuários do dump para Django')

    # -----------------------------------------------------------------------

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.apenas_mapeamento = options['apenas_mapeamento']
        self.incluir_usuarios = options['incluir_usuarios']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('\n!  MODO DRY-RUN — nenhum dado será gravado\n'))

        # Ler e parsear o dump
        sql_file = options['sql_file']
        self.stdout.write(f'Lendo dump: {sql_file} ...')
        try:
            dump = MySQLDumpParser(sql_file)
        except FileNotFoundError:
            raise CommandError(f'Arquivo não encontrado: {sql_file}')
        except Exception as exc:
            raise CommandError(f'Erro ao ler o dump: {exc}')

        tabelas = dump.tabelas_disponiveis()
        self.stdout.write(f'Tabelas encontradas no dump: {", ".join(tabelas)}\n')

        # -- Fase 1: Mapeamentos ------------------------------------------
        self._secao('FASE 1 — Mapeamento de IDs')

        map_cargos      = self._mapear_cargos(dump)
        map_cidades     = self._mapear_cidades(dump)
        map_unidades    = self._mapear_unidades(dump)
        map_autoridades = self._mapear_autoridades(dump, map_cargos)
        map_servicos    = self._mapear_servicos(dump)
        map_users       = self._mapear_users(dump, map_unidades, map_servicos)

        for nome, m in [
            ('Cargos', map_cargos),
            ('Cidades/Municípios', map_cidades),
            ('Unidades Demandantes', map_unidades),
            ('Autoridades', map_autoridades),
            ('Serviços Periciais', map_servicos),
            ('Usuários', map_users),
        ]:
            self.stdout.write(f'  {nome}: {len(m)} mapeados')

        if self.apenas_mapeamento:
            self._detalhar_mapeamentos(dump, map_cargos, map_cidades, map_unidades,
                                       map_autoridades, map_servicos, map_users)
            self.stdout.write('\n(--apenas-mapeamento: encerrando sem migrar dados)\n')
            return

        # -- Fase 2: Usuários (opcional) ----------------------------------
        if self.incluir_usuarios:
            self._secao('FASE 2 -- Usuarios')
            # Sem atomic externo: cada usuário usa savepoint interno
            self._migrar_usuarios(dump, map_unidades, map_servicos)
            # Reconstruir mapeamento com os recém-criados
            map_users = self._mapear_users(dump, map_unidades, map_servicos)

        # -- Fase 3: Custódia --------------------------------------------─
        self._secao('FASE 3 — Dados de Custódia')

        if not self.dry_run:
            with transaction.atomic():
                map_vest = self._migrar_vestigios(dump, map_unidades, map_servicos,
                                                  map_autoridades, map_users)
                self._migrar_movimentacoes(dump, map_vest, map_unidades, map_servicos,
                                           map_autoridades, map_users)
                self._migrar_dnas(dump, map_vest, map_users)
        else:
            map_vest = self._migrar_vestigios(dump, map_unidades, map_servicos,
                                              map_autoridades, map_users)
            self._migrar_movimentacoes(dump, map_vest, map_unidades, map_servicos,
                                       map_autoridades, map_users)
            self._migrar_dnas(dump, map_vest, map_users)

        self.stdout.write(self.style.SUCCESS('\nOK Migração concluída!\n'))

    # -----------------------------------------------------------------------
    # Fase 1 — Mapeamentos
    # -----------------------------------------------------------------------

    def _mapear_cargos(self, dump: MySQLDumpParser) -> dict:
        django_idx = {normalizar(c.nome): c.id for c in Cargo.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in dump.tabela('cargos'):
            chave = normalizar(row.get('nome', ''))
            if chave in django_idx:
                mapeamento[row['id']] = django_idx[chave]
            else:
                nao_encontrados.append(row)

        for r in nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  [Cargo] NÃO ENCONTRADO mysql_id={r["id"]} nome="{r["nome"]}"'))
            if not self.dry_run:
                try:
                    obj = Cargo(nome=str(r['nome']).strip().upper())
                    obj.save()
                    mapeamento[r['id']] = obj.id
                    self.stdout.write(f'    -> criado django_id={obj.id}')
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'    ERRO: {exc}'))

        return mapeamento

    def _mapear_cidades(self, dump: MySQLDumpParser) -> dict:
        django_idx = {normalizar(c.nome): c.id for c in Cidade.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in dump.tabela('municipios'):
            chave = normalizar(row.get('nome', ''))
            if chave in django_idx:
                mapeamento[row['id']] = django_idx[chave]
            else:
                nao_encontrados.append(row)

        for r in nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  [Cidade] NÃO ENCONTRADA mysql_id={r["id"]} nome="{r["nome"]}"'))
            if not self.dry_run:
                try:
                    obj = Cidade(nome=str(r['nome']).strip().upper())
                    obj.save()
                    mapeamento[r['id']] = obj.id
                    self.stdout.write(f'    -> criada django_id={obj.id}')
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'    ERRO: {exc}'))

        return mapeamento

    def _mapear_unidades(self, dump: MySQLDumpParser) -> dict:
        """MySQL não tem 'sigla' -> match por nome normalizado."""
        django_por_nome  = {normalizar(u.nome):  u.id for u in UnidadeDemandante.all_objects.all()}
        django_por_sigla = {normalizar(u.sigla): u.id for u in UnidadeDemandante.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in dump.tabela('unidades_demandantes'):
            nome = row.get('nome', '') or ''
            chave_nome  = normalizar(nome)
            sigla_der   = normalizar(sigla_de_nome(nome))

            if chave_nome in django_por_nome:
                mapeamento[row['id']] = django_por_nome[chave_nome]
            elif sigla_der in django_por_sigla:
                mapeamento[row['id']] = django_por_sigla[sigla_der]
                self.stdout.write(
                    f'  [Unidade] "{nome}" mapeada via sigla derivada "{sigla_der}"')
            else:
                nao_encontrados.append(row)

        for r in nao_encontrados:
            nome = r.get('nome', '') or ''
            sigla = sigla_de_nome(nome)
            self.stdout.write(self.style.WARNING(
                f'  [Unidade] NÃO ENCONTRADA mysql_id={r["id"]} nome="{nome}" '
                f'(sigla derivada="{sigla}")'))
            if not self.dry_run:
                try:
                    obj = UnidadeDemandante(
                        nome=nome.strip().upper(),
                        sigla=sigla,
                    )
                    obj.save()
                    mapeamento[r['id']] = obj.id
                    self.stdout.write(f'    -> criada django_id={obj.id}')
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'    ERRO: {exc}'))

        return mapeamento

    def _mapear_autoridades(self, dump: MySQLDumpParser, map_cargos: dict) -> dict:
        django_idx = {normalizar(a.nome): a.id for a in Autoridade.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in dump.tabela('autoridades'):
            chave = normalizar(row.get('nome', ''))
            if chave in django_idx:
                mapeamento[row['id']] = django_idx[chave]
            else:
                nao_encontrados.append(row)

        for r in nao_encontrados:
            django_cargo_id = map_cargos.get(r.get('cargo_id'))
            self.stdout.write(self.style.WARNING(
                f'  [Autoridade] NÃO ENCONTRADA mysql_id={r["id"]} nome="{r["nome"]}"'))
            if not self.dry_run and django_cargo_id:
                try:
                    cargo = Cargo.all_objects.get(pk=django_cargo_id)
                    obj = Autoridade(
                        nome=str(r['nome']).strip().upper(),
                        cargo=cargo,
                    )
                    obj.save()
                    mapeamento[r['id']] = obj.id
                    self.stdout.write(f'    -> criada django_id={obj.id}')
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'    ERRO: {exc}'))
            elif not django_cargo_id:
                self.stdout.write('    -> IGNORADA (cargo não mapeado)')

        return mapeamento

    def _mapear_servicos(self, dump: MySQLDumpParser) -> dict:
        """MySQL tem sigla -> usa sigla como chave primária."""
        django_por_sigla = {normalizar(s.sigla): s.id for s in ServicoPericial.all_objects.all()}
        django_por_nome  = {normalizar(s.nome):  s.id for s in ServicoPericial.all_objects.all()}
        mapeamento = {}
        nao_encontrados = []

        for row in dump.tabela('servicos_peciricais'):
            sigla = row.get('sigla') or ''
            nome  = row.get('nome') or ''
            cs, cn = normalizar(sigla), normalizar(nome)

            if cs and cs in django_por_sigla:
                mapeamento[row['id']] = django_por_sigla[cs]
            elif cn and cn in django_por_nome:
                mapeamento[row['id']] = django_por_nome[cn]
            else:
                nao_encontrados.append(row)

        for r in nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  [Serviço] NÃO ENCONTRADO mysql_id={r["id"]} '
                f'sigla="{r.get("sigla")}" nome="{r.get("nome")}"'))
            if not self.dry_run:
                try:
                    obj = ServicoPericial(
                        sigla=(r.get('sigla') or '').strip().upper(),
                        nome=(r.get('nome') or '').strip().upper(),
                    )
                    obj.save()
                    mapeamento[r['id']] = obj.id
                    self.stdout.write(f'    -> criado django_id={obj.id}')
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'    ERRO: {exc}'))

        return mapeamento

    def _mapear_users(self, dump: MySQLDumpParser, map_unidades: dict, map_servicos: dict) -> dict:
        """Match por CPF (chave natural mais confiável)."""
        django_idx = {}
        for u in User.all_objects.all():
            if u.cpf:
                cpf_limpo = u.cpf.replace('.', '').replace('-', '').strip()
                django_idx[cpf_limpo] = u.id

        mapeamento = {}
        nao_encontrados = []

        for row in dump.tabela('users'):
            cpf = (row.get('cpf') or '').replace('.', '').replace('-', '').strip()
            if cpf and cpf in django_idx:
                mapeamento[row['id']] = django_idx[cpf]
            else:
                nao_encontrados.append(row)

        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'  [Usuários] {len(nao_encontrados)} sem correspondência em Django:'))
            for r in nao_encontrados:
                self.stdout.write(
                    f'    mysql_id={r["id"]} cpf="{r.get("cpf")}" email="{r.get("email")}"')
            if not self.incluir_usuarios:
                self.stdout.write('    -> Use --incluir-usuarios para criá-los.')

        return mapeamento

    # -----------------------------------------------------------------------
    # Fase 2 — Usuários
    # -----------------------------------------------------------------------

    def _migrar_usuarios(self, dump: MySQLDumpParser, map_unidades: dict, map_servicos: dict):
        # Carregar roles: {user_mysql_id: role_name}
        roles_idx: dict[int, str] = {}
        roles_table = {r['id']: r['role_name'] for r in dump.tabela('roles')}
        for r in dump.tabela('users_roles'):
            roles_idx[r['user_id']] = roles_table.get(r['role_id'], 'ROLE_PERITO')

        criados = skipped = erros = 0

        for row in dump.tabela('users'):
            cpf   = (row.get('cpf')   or '').strip()
            email = (row.get('email') or '').strip()
            if not cpf:
                skipped += 1
                continue
            # Pular se já existe por CPF OU por email (evita IntegrityError)
            if (User.all_objects.filter(cpf=cpf).exists() or
                    (email and User.all_objects.filter(email=email).exists())):
                skipped += 1
                continue

            perfil     = ROLE_PARA_PERFIL.get(roles_idx.get(row['id'], ''), 'PERITO')
            unidade_id = map_unidades.get(row.get('unidade_demandante_id'))
            servico_id = map_servicos.get(row.get('servico_pericial_id'))

            if self.dry_run:
                self.stdout.write(
                    f'  DRY cpf={cpf} email={email} perfil={perfil} -> seria criado')
                criados += 1
                continue

            # Usar savepoint por usuário para que um erro não quebre a transação toda
            try:
                with transaction.atomic():
                    user = User(
                        email=email or f'{cpf}@migrado.local',
                        cpf=cpf,
                        nome_completo=row.get('fullname') or '',
                        status='ATIVO' if to_bool(row.get('enabled')) else 'INATIVO',
                        perfil=perfil,
                        deve_alterar_senha=True,
                    )
                    # Senha BCrypt Java compatível com Django — importar diretamente
                    user.password = row.get('password') or ''
                    if unidade_id:
                        user.unidade_demandante_id = unidade_id
                    user.save()
                    if servico_id:
                        user.servicos_periciais.add(servico_id)
                criados += 1
            except Exception as exc:
                erros += 1
                self.stdout.write(self.style.ERROR(f'  ERRO cpf={cpf}: {exc}'))

        self._log('Usuários', criados, skipped, erros)

    # -----------------------------------------------------------------------
    # Fase 3 — Custódia
    # -----------------------------------------------------------------------

    def _migrar_vestigios(self, dump, map_unidades, map_servicos, map_autoridades, map_users) -> dict:
        """
        Retorna {mysql_id: django_id} — necessário para movimentações e DNAs.

        Colunas MySQL que NÃO existem em Django:
          (nenhuma — o Django tem campos a mais, não a menos)

        Colunas Django que NÃO existem no MySQL:
          contra_prova (self-FK) -> NULL
          responsavel_nome -> ''
        """
        rows = dump.tabela('vestigios')
        mapeamento = {}
        criados = skipped = erros = 0
        objs_bulk = []
        mysql_ids_bulk = []

        for row in rows:
            unidade_id = map_unidades.get(row.get('unidade_demandante_id'))
            if not unidade_id:
                self.stdout.write(self.style.WARNING(
                    f'  [Vestígio] mysql_id={row["id"]} ignorado: '
                    f'unidade_demandante_id={row.get("unidade_demandante_id")} não mapeada'))
                erros += 1
                continue

            if self.dry_run:
                criados += 1
                continue

            status = row.get('status') or 'INICIAL'
            if status not in STATUS_VESTIGIO:
                status = 'INICIAL'

            objs_bulk.append(Vestigio(
                lacre=row.get('lacre') or '',
                num_processo_sei=row.get('num_processo_sei') or '',
                conformidade=to_bool(row.get('conformidade')),
                biologico=to_bool(row.get('biologico')),
                ocorrencia=row.get('ocorrencia') or '',
                ano_ocorrencia=row.get('ano_ocorrencia'),
                status=status,
                descricao=row.get('descricao') or '',
                saiu_da_custodia=to_bool(row.get('saiu_da_custodia')),
                unidade_demandante_id=unidade_id,
                servico_pericial_id=map_servicos.get(row.get('servico_pericial_id')),
                autoridade_id=map_autoridades.get(row.get('autoridade_id')),
                user_destino_id=map_users.get(row.get('user_destino_id')),
                created_by_id=map_users.get(row.get('user_created_id')),
                updated_by_id=map_users.get(row.get('user_updated_id')),
                created_at=to_datetime(row.get('created_at')),
                updated_at=to_datetime(row.get('updated_at')),
            ))
            mysql_ids_bulk.append(row['id'])

        if objs_bulk:
            try:
                criados_objs = Vestigio.objects.bulk_create(objs_bulk, batch_size=200)
                criados = len(criados_objs)
                # Preservar timestamps originais (bulk_create bypassa auto_now)
                for obj, ts_original in zip(criados_objs, [
                    (to_datetime(r.get('created_at')), to_datetime(r.get('updated_at')))
                    for r in rows if map_unidades.get(r.get('unidade_demandante_id'))
                ]):
                    Vestigio.objects.filter(pk=obj.pk).update(
                        created_at=ts_original[0],
                        updated_at=ts_original[1],
                    )
                for mysql_id, obj in zip(mysql_ids_bulk, criados_objs):
                    mapeamento[mysql_id] = obj.pk
            except Exception as exc:
                erros += len(objs_bulk)
                self.stdout.write(self.style.ERROR(f'  ERRO bulk vestígios: {exc}'))

        self._log('Vestígios', criados, skipped, erros)
        return mapeamento

    def _migrar_movimentacoes(self, dump, map_vestigios, map_unidades, map_servicos, map_autoridades, map_users):
        rows = dump.tabela('vestigios_movimentacoes')
        criados = skipped = erros = 0
        objs = []

        for row in rows:
            vest_id = map_vestigios.get(row.get('vestigio_id'))
            if not vest_id:
                skipped += 1
                continue

            if self.dry_run:
                criados += 1
                continue

            ts = to_datetime(row.get('created_at'))
            objs.append(VestigioMovimentacao(
                vestigio_id=vest_id,
                lacre=row.get('lacre') or '',
                num_processo_sei=row.get('num_processo_sei') or '',
                descricao=row.get('descricao') or '',
                aceito=to_bool(row.get('aceito')),
                data_hora_aceito=to_datetime(row.get('data_hora_aceito')),
                unidade_demandante_id=map_unidades.get(row.get('unidade_demandante_id')),
                servico_pericial_id=map_servicos.get(row.get('servico_pericial_id')),
                autoridade_id=map_autoridades.get(row.get('autoridade_id')),
                user_destino_id=map_users.get(row.get('user_destino_id')),
                created_by_id=map_users.get(row.get('user_created_id')),
                created_at=ts,
                updated_at=ts,
            ))

        if objs:
            try:
                VestigioMovimentacao.objects.bulk_create(objs, batch_size=300)
                criados = len(objs)
            except Exception as exc:
                erros = len(objs)
                self.stdout.write(self.style.ERROR(f'  ERRO bulk movimentações: {exc}'))

        self._log('Movimentações', criados, skipped, erros)

    def _migrar_dnas(self, dump, map_vestigios, map_users):
        """
        Colunas MySQL -> Django:
          gemeo/tranfusao/transplante : int -> SimNao
          tranfusao (typo)            -> transfusao
          nascimento/data_da_coleta   : date str -> datetime
          situacao                    : não existe no MySQL -> 'NAO_APENADO'
          processado_banco_perfis_genetico : não existe -> 'NAO'
          estrangeiro                 : não existe -> False
          registrado_por_usuario_externo : não existe -> False
        """
        rows = dump.tabela('dnas')
        criados = skipped = erros = 0
        objs = []

        for row in rows:
            if self.dry_run:
                criados += 1
                continue

            objs.append(DNA(
                nome=row.get('nome') or '',
                cpf=row.get('cpf') or '',
                rg=row.get('rg') or '',
                nascimento=to_datetime(row.get('nascimento')),
                naturalidade=row.get('naturalidade') or '',
                estrangeiro=False,
                uf=row.get('uf') or '',
                mae=row.get('mae') or '',
                pai=row.get('pai') or '',
                pais=row.get('pais') or '',
                gemeo=INT_PARA_SIMNO.get(row.get('gemeo'), 'NAO'),
                transfusao=INT_PARA_SIMNO.get(row.get('tranfusao'), 'NAO'),  # typo resolvido
                transplante=INT_PARA_SIMNO.get(row.get('transplante'), 'NAO'),
                processado_banco_perfis_genetico='NAO',
                unidade_prisional=row.get('unidade_prisional') or '',
                tipo_penal=row.get('tipo_penal') or '',
                data_da_coleta=to_datetime(row.get('data_da_coleta')),
                lacres=row.get('lacres') or '',
                testemunha=row.get('testemunha') or '',
                testemunha2=row.get('testemunha2') or '',
                notas=row.get('notas') or '',
                ocorrencia=row.get('ocorrencia') or '',
                processo_judicial=row.get('processo_judicial') or '',
                num_processo_sei=row.get('num_processo_sei') or '',
                finalidade_coleta=row.get('finalidade_coleta') or 'LEI',
                codigo_barras=row.get('codigo_barras') or '',
                situacao='NAO_APENADO',
                responsavel_coleta='',
                registrado_por_usuario_externo=False,
                nome_foto=row.get('nome_foto') or '',
                perito_id=map_users.get(row.get('perito_id')),
                vestigio_id=map_vestigios.get(row.get('vestigio_id')) if row.get('vestigio_id') else None,
                created_by_id=map_users.get(row.get('user_created_id')),
                updated_by_id=map_users.get(row.get('user_updated_id')),
                created_at=to_datetime(row.get('created_at')),
                updated_at=to_datetime(row.get('updated_at')),
            ))

        if objs:
            try:
                DNA.objects.bulk_create(objs, batch_size=300)
                criados = len(objs)
            except Exception as exc:
                erros = len(objs)
                self.stdout.write(self.style.ERROR(f'  ERRO bulk DNA: {exc}'))

        self._log('Registros DNA', criados, skipped, erros)
        if not self.dry_run and criados:
            self.stdout.write(self.style.WARNING(
                '  !  Arquivos de foto NÃO foram copiados.\n'
                '     Copie de: <pasta uploads do Java>  ->  media/custodia/dna/fotos/'))

    # -----------------------------------------------------------------------
    # Utilitários
    # -----------------------------------------------------------------------

    def _detalhar_mapeamentos(self, dump, map_cargos, map_cidades, map_unidades,
                               map_autoridades, map_servicos, map_users):
        self._secao('DETALHE DOS MAPEAMENTOS')
        tabelas_map = [
            ('cargos',                  map_cargos,      'nome'),
            ('municipios',              map_cidades,     'nome'),
            ('unidades_demandantes',    map_unidades,    'nome'),
            ('autoridades',             map_autoridades, 'nome'),
            ('servicos_peciricais',     map_servicos,    'sigla'),
            ('users',                   map_users,       'cpf'),
        ]
        for tabela, mapeamento, campo_nome in tabelas_map:
            self.stdout.write(f'\n  {tabela}:')
            for row in dump.tabela(tabela):
                mid = row['id']
                did = mapeamento.get(mid)
                status = f'-> django_id={did}' if did else self.style.ERROR('-> NÃO MAPEADO')
                self.stdout.write(f'    mysql_id={mid:4d} {campo_nome}="{row.get(campo_nome)}"  {status}')

    def _secao(self, titulo):
        self.stdout.write(f'\n{"-" * 65}')
        self.stdout.write(f'  {titulo}')
        self.stdout.write('-' * 65)

    def _log(self, entidade, criados, skipped, erros):
        partes = [f'  {entidade}: {criados} criados']
        if skipped:
            partes.append(f'{skipped} pulados')
        if erros:
            partes.append(self.style.ERROR(f'{erros} erros'))
        self.stdout.write(', '.join(partes))
