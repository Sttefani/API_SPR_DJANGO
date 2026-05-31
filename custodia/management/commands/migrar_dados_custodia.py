# custodia/management/commands/migrar_dados_custodia.py
#
# ETL: lê o dump MySQL do SPR-Custódia e grava no PostgreSQL via ORM Django.
# Uso: python manage.py migrar_dados_custodia [--dump CAMINHO]
#
# Ordem de migração (respeita FKs):
#   municipios → cidades.Cidade
#   cargos → cargos.Cargo
#   servicos_peciricais → servicos_periciais.ServicoPericial
#   autoridades → autoridades.Autoridade
#   unidades_demandantes → unidades_demandantes.UnidadeDemandante
#   vestigios → custodia.Vestigio
#   vestigios_movimentacoes → custodia.VestigioMovimentacao
#   dnas → custodia.DNA
#
# Usuários do Custódia NÃO são migrados (sistema próprio de auth no Django).
# Campos created_by/updated_by/user_destino/perito ficam nulos.

import re
import unicodedata
from datetime import datetime, date
from django.core.management.base import BaseCommand
from django.db import transaction

DUMP_PADRAO = r'C:\dev\spr-custodia\config servidor\criminalistica_vestigios_2025-05-12_12-00-02.sql'


def _fix_encoding(s: str) -> str:
    """
    Corrige o encoding duplo que ocorre quando bytes UTF-8 foram lidos como Latin-1.
    Ex: 'Ã§' (bytes C3 A7 lidos como latin-1) → 'ç' (U+00E7)
        'Âº' (bytes C2 BA lidos como latin-1) → 'º' (U+00BA)
    Se a string já está em Latin-1 nativo (ex: byte 0xE7 = 'ç'), encode('latin-1')
    retorna 0xE7 que é inválido como UTF-8 de 1 byte — cai no except e retorna 's'.
    """
    if not s:
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


# ---------------------------------------------------------------------------
# Parser de dump MySQL
# ---------------------------------------------------------------------------

def _parse_valor(s, i):
    """
    Lê um valor MySQL a partir da posição i na string s.
    Retorna (valor_python, nova_posição).
    Trata: NULL, strings '...', _binary '...', inteiros, floats.
    """
    n = len(s)

    # NULL
    if s[i:i+4] == 'NULL':
        return None, i + 4

    # _binary '...'  (campos bit(1))
    if s[i:i+8] == '_binary ':
        i += 8
        if i < n and s[i] == "'":
            i += 1
            raw = []
            while i < n:
                c = s[i]
                if c == '\\' and i + 1 < n:
                    nc = s[i + 1]
                    raw.append('\x00' if nc == '0' else nc)
                    i += 2
                elif c == "'":
                    i += 1
                    break
                else:
                    raw.append(c)
                    i += 1
            content = ''.join(raw)
            return content not in ('\x00', ''), i
        return False, i

    # String '...'
    if s[i] == "'":
        i += 1
        chars = []
        while i < n:
            c = s[i]
            if c == '\\' and i + 1 < n:
                nc = s[i + 1]
                esc = {
                    'n': '\n', 'r': '\r', 't': '\t',
                    '\\': '\\', "'": "'", '0': '\x00',
                    'Z': '\x1a',
                }
                chars.append(esc.get(nc, nc))
                i += 2
            elif c == "'":
                # MySQL também usa '' para escapar aspas dentro de strings
                if i + 1 < n and s[i + 1] == "'":
                    chars.append("'")
                    i += 2
                else:
                    i += 1
                    break
            else:
                chars.append(c)
                i += 1
        return _fix_encoding(''.join(chars)), i

    # Número (inteiro ou float, possivelmente negativo)
    start = i
    if i < n and s[i] == '-':
        i += 1
    while i < n and (s[i].isdigit() or s[i] == '.'):
        i += 1
    num_str = s[start:i]
    if not num_str or num_str == '-':
        # não reconhecido — avança um char para não travar
        return None, i + 1
    return (float(num_str) if '.' in num_str else int(num_str)), i


def _parse_linhas(values_str):
    """
    Recebe a string de VALUES de um INSERT e retorna lista de listas
    (cada lista = uma linha/tupla de valores Python).
    """
    rows = []
    i = 0
    n = len(values_str)

    while i < n:
        # avança até '('
        while i < n and values_str[i] != '(':
            i += 1
        if i >= n:
            break
        i += 1  # consome '('

        row = []
        while i < n:
            # pula espaços
            while i < n and values_str[i] in (' ', '\t', '\n', '\r'):
                i += 1
            if i >= n or values_str[i] == ')':
                break
            val, i = _parse_valor(values_str, i)
            row.append(val)
            # pula vírgula/espaços entre valores
            while i < n and values_str[i] in (' ', '\t', '\n', '\r', ','):
                if values_str[i] == ',':
                    i += 1
                    break
                i += 1

        i += 1  # consome ')'
        rows.append(row)

        # pula vírgula/espaços entre tuplas
        while i < n and values_str[i] in (' ', '\t', '\n', '\r', ','):
            i += 1

    return rows


def extrair_tabelas(dump_path):
    """
    Lê o dump e devolve dict {nome_tabela: [lista_de_linhas]}.
    Usa latin-1 para preservar os bytes brutos. Cada string é depois corrigida
    por _fix_encoding() que resolve o duplo encoding UTF-8-via-latin-1.
    """
    with open(dump_path, 'rb') as f:
        conteudo = f.read().decode('latin-1')

    tabelas = {}
    # Usa lookahead para não terminar no ; dentro de strings:
    # o INSERT termina com ;\n seguido de UNLOCK ou /*!
    padrao = re.compile(
        r"INSERT INTO `([^`]+)` VALUES\s*(.+?);\s*\n\s*(?=UNLOCK|/\*!)",
        re.DOTALL,
    )
    for m in padrao.finditer(conteudo):
        nome = m.group(1)
        if nome.endswith('_aud') or nome in ('revinfo', 'reports', 'roles'):
            continue
        tabelas[nome] = _parse_linhas(m.group(2))

    return tabelas


def construir_mapa_usuarios(tabelas):
    """
    Constrói {java_user_id: (django_user | None, nome_completo_str)}.

    Tenta casar cada usuário Java com um usuário Django pelo CPF (campo
    mais confiável e imutável). Se não encontrar no Django, guarda o nome
    do dump para preencher responsavel_nome (não repúdio).

    Colunas do dump (CREATE TABLE users):
      id, cpf, created_at, data_nascimento, deve_alterar_senha, email,
      nome_completo, password, status, telefone_celular,
      user_created_id, user_updated_id
    """
    from usuarios.models import User as DjangoUser

    linhas_users = tabelas.get('users', [])
    mapa = {}   # java_id → (django_user_or_None, nome_str)

    # Cache Django: CPF normalizado → User
    django_por_cpf = {}
    for du in DjangoUser.all_objects.all():
        cpf_limpo = ''.join(filter(str.isdigit, du.cpf or ''))
        if cpf_limpo:
            django_por_cpf[cpf_limpo] = du

    for row in linhas_users:
        # Colunas do dump SPR-Custodia Java (CREATE TABLE users):
        # 0:id  1:cpf  2:email  3:enabled(bit)  4:fullname
        # 5:password  6:username  7:unidade_demandante_id  8:servico_pericial_id
        if len(row) < 5:
            continue
        java_id   = row[0]
        cpf_java  = _str(row[1]) or ''
        nome_java = _fix_encoding(_str(row[4]) or '').strip()  # fullname, não username

        cpf_limpo = ''.join(filter(str.isdigit, cpf_java))
        django_user = django_por_cpf.get(cpf_limpo)

        mapa[java_id] = (django_user, nome_java)

    return mapa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str(val, upper=False, truncar=None):
    if val is None:
        return None
    s = str(val).strip()
    if upper:
        s = s.upper()
    if truncar:
        s = s[:truncar]
    return s or None


def _bool(val):
    """Converte valor bit(1) já parseado (bool ou int) para bool Python."""
    if isinstance(val, bool):
        return val
    return bool(val)


def _simNao(val):
    """Converte int 0/1 do dump para 'YES'/'NO' (choices DNA.SimNao)."""
    return 'YES' if val else 'NO'


def _datetime(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _gerar_sigla(nome):
    """
    Extrai/gera sigla para UnidadeDemandante a partir do nome.
    Prioridade: parte antes de ' - ' se existir, senão iniciais.
    """
    if ' - ' in nome:
        sigla = nome.split(' - ')[0].strip()
    else:
        skip = {'DE', 'DO', 'DA', 'DOS', 'DAS', 'E', 'A', 'O', 'EM', 'COM'}
        sigla = ''.join(
            p[0] for p in nome.upper().split() if p not in skip
        )
    # garante apenas ASCII alfanumérico + pontuação básica, max 20
    sigla = re.sub(r'[^A-ZÀ-Ú0-9.\-º/]', '', sigla.upper())
    return sigla[:20] or nome[:20].upper()


# ---------------------------------------------------------------------------
# Funções de migração por tabela
# ---------------------------------------------------------------------------

def migrar_municipios(linhas, stdout):
    from cidades.models import Cidade
    criados, existentes = 0, 0
    for row in linhas:
        # colunas: id, created_at, nome, updated_at, user_created_id, user_updated_id
        nome = _str(row[2], upper=True)
        if not nome:
            continue
        _, created = Cidade.all_objects.get_or_create(nome=nome)
        if created:
            criados += 1
        else:
            existentes += 1
    stdout.write(f'  Municípios: {criados} criados, {existentes} já existiam')


def migrar_cargos(linhas, stdout):
    from cargos.models import Cargo

    id_map = {}  # mysql_id → django_obj
    criados, existentes = 0, 0
    for row in linhas:
        # colunas: id, created_at, nome, updated_at, user_created_id, user_updated_id
        mysql_id = row[0]
        nome = _str(row[2], upper=True)
        if not nome:
            continue
        obj, created = Cargo.all_objects.get_or_create(nome=nome)
        id_map[mysql_id] = obj
        if created:
            criados += 1
        else:
            existentes += 1
    stdout.write(f'  Cargos: {criados} criados, {existentes} já existiam')
    return id_map


def migrar_servicos(linhas, stdout):
    from servicos_periciais.models import ServicoPericial

    id_map = {}
    criados, existentes = 0, 0
    for row in linhas:
        # colunas: id, created_at, nome, sigla, updated_at, user_created_id, user_updated_id
        mysql_id = row[0]
        nome = _str(row[2], upper=True, truncar=50)
        sigla = _str(row[3], upper=True, truncar=10)
        if not nome or not sigla:
            continue

        # usa all_objects para não perder registros com soft-delete
        obj = ServicoPericial.all_objects.filter(sigla=sigla).first()
        if obj is None:
            obj = ServicoPericial.all_objects.filter(nome=nome).first()
        if obj is None:
            obj = ServicoPericial(sigla=sigla, nome=nome)
            obj.save()
            criados += 1
        else:
            existentes += 1
        id_map[mysql_id] = obj
    stdout.write(f'  Serviços Periciais: {criados} criados, {existentes} já existiam')
    return id_map


def migrar_autoridades(linhas, cargo_map, stdout):
    from autoridades.models import Autoridade

    id_map = {}
    criados, existentes, ignorados = 0, 0, 0
    for row in linhas:
        # colunas: id, created_at, nome, updated_at, cargo_id, user_created_id, user_updated_id
        mysql_id = row[0]
        nome = _str(row[2], upper=True)
        cargo_id_mysql = row[4]

        if not nome:
            ignorados += 1
            continue

        cargo = cargo_map.get(cargo_id_mysql)
        if cargo is None:
            ignorados += 1
            continue

        obj = Autoridade.all_objects.filter(nome=nome).first()
        if obj is None:
            obj = Autoridade(nome=nome, cargo=cargo)
            obj.save()
            criados += 1
        else:
            existentes += 1
        id_map[mysql_id] = obj
    stdout.write(
        f'  Autoridades: {criados} criadas, {existentes} já existiam, {ignorados} ignoradas'
    )
    return id_map


def migrar_unidades(linhas, stdout):
    from unidades_demandantes.models import UnidadeDemandante

    id_map = {}
    criados, existentes = 0, 0
    siglas_usadas = set(
        UnidadeDemandante.all_objects.values_list('sigla', flat=True)
    )

    for row in linhas:
        # colunas: id, created_at, nome, updated_at, user_created_id, municipio_id, user_updated_id
        mysql_id = row[0]
        nome = _str(row[2])
        if not nome:
            continue

        nome_upper = nome.upper()
        obj = UnidadeDemandante.all_objects.filter(nome=nome_upper).first()
        if obj is None:
            sigla = _gerar_sigla(nome)
            # garante unicidade da sigla
            base_sigla = sigla
            contador = 2
            while sigla in siglas_usadas:
                sufixo = str(contador)
                sigla = base_sigla[:20 - len(sufixo)] + sufixo
                contador += 1
            siglas_usadas.add(sigla)

            obj = UnidadeDemandante(sigla=sigla, nome=nome_upper)
            obj.save()
            criados += 1
        else:
            existentes += 1
        id_map[mysql_id] = obj
    stdout.write(
        f'  Unidades Demandantes: {criados} criadas, {existentes} já existiam'
    )
    return id_map


def migrar_vestigios(linhas, unidade_map, servico_map, autoridade_map, user_map, stdout):
    from custodia.models import Vestigio

    id_map = {}
    criados, erros = 0, 0
    sem_usuario = 0

    for row in linhas:
        # colunas (ordem do CREATE TABLE):
        # 0:id, 1:ano_ocorrencia, 2:biologico(bit), 3:conformidade(bit),
        # 4:created_at, 5:descricao, 6:lacre, 7:ocorrencia, 8:status,
        # 9:updated_at, 10:autoridade_id, 11:user_created_id,
        # 12:servico_pericial_id, 13:unidade_demandante_id, 14:user_updated_id,
        # 15:user_destino_id, 16:num_processo_sei, 17:saiu_da_custodia(bit)
        try:
            mysql_id = row[0]
            unidade = unidade_map.get(row[13])
            servico = servico_map.get(row[12])

            if unidade is None or servico is None:
                erros += 1
                continue

            # Mapeia usuário criador (não repúdio)
            django_user, nome_java = user_map.get(row[11], (None, None))
            if django_user is None:
                sem_usuario += 1

            obj = Vestigio(
                ano_ocorrencia=row[1],
                biologico=_bool(row[2]),
                conformidade=_bool(row[3]),
                descricao=_str(row[5]),
                lacre=_str(row[6]),
                ocorrencia=_str(row[7]),
                status=_str(row[8]) or Vestigio.Status.INICIAL,
                autoridade=autoridade_map.get(row[10]),
                servico_pericial=servico,
                unidade_demandante=unidade,
                num_processo_sei=_str(row[16]),
                saiu_da_custodia=_bool(row[17]),
                created_by=django_user,
                responsavel_nome=None if django_user else nome_java,
            )
            obj.save()
            id_map[mysql_id] = obj
            criados += 1
        except Exception as e:
            erros += 1
            stdout.write(f'  [WARN] Vestígio id={row[0]}: {e}')

    stdout.write(
        f'  Vestígios: {criados} criados, {erros} erros '
        f'({criados - sem_usuario} com usuário Django, {sem_usuario} com nome de fallback)'
    )
    return id_map


def migrar_movimentacoes(linhas, vestigio_map, unidade_map, servico_map, autoridade_map, user_map, stdout):
    from custodia.models import VestigioMovimentacao

    criados, erros, sem_usuario = 0, 0, 0
    for row in linhas:
        # colunas:
        # 0:id, 1:aceito(bit), 2:created_at, 3:data_hora_aceito,
        # 4:descricao, 5:lacre, 6:autoridade_id, 7:user_created_id,
        # 8:servico_pericial_id, 9:unidade_demandante_id,
        # 10:user_destino_id, 11:vestigio_id, 12:num_processo_sei
        try:
            vestigio = vestigio_map.get(row[11])
            if vestigio is None:
                erros += 1
                continue

            # Mapeia usuário criador (não repúdio)
            django_user, nome_java = user_map.get(row[7], (None, None))
            if django_user is None:
                sem_usuario += 1

            obj = VestigioMovimentacao(
                vestigio=vestigio,
                aceito=_bool(row[1]),
                data_hora_aceito=_datetime(row[3]),
                descricao=_str(row[4]),
                lacre=_str(row[5]),
                autoridade=autoridade_map.get(row[6]),
                servico_pericial=servico_map.get(row[8]),
                unidade_demandante=unidade_map.get(row[9]),
                num_processo_sei=_str(row[12]),
                created_by=django_user,
                responsavel_nome=None if django_user else nome_java,
            )
            obj.save()
            criados += 1
        except Exception as e:
            erros += 1
            stdout.write(f'  [WARN] Movimentação id={row[0]}: {e}')

    stdout.write(
        f'  Movimentações: {criados} criadas, {erros} erros '
        f'({criados - sem_usuario} com usuário Django, {sem_usuario} com nome de fallback)'
    )


def migrar_dnas(linhas, vestigio_map, stdout):
    from custodia.models import DNA

    criados, erros = 0, 0
    for row in linhas:
        # colunas (ordem do CREATE TABLE):
        # 0:id, 1:cpf, 2:created_at, 3:data_da_coleta(date), 4:foto,
        # 5:gemeo(int), 6:lacres, 7:mae, 8:nascimento(date), 9:naturalidade,
        # 10:nome, 11:notas, 12:pai, 13:rg, 14:testemunha, 15:testemunha2,
        # 16:tipo_penal, 17:tranfusao(int,typo), 18:transplante(int),
        # 19:uf, 20:unidade_prisional, 21:updated_at, 22:user_created_id,
        # 23:perito_id, 24:user_updated_id, 25:nome_foto, 26:vestigio_id,
        # 27:codigo_barras, 28:finalidade_coleta, 29:num_processo_sei,
        # 30:ocorrencia, 31:pais, 32:processo_judicial
        try:
            nome = _str(row[10])
            cpf = _str(row[1])
            mae = _str(row[7])
            rg = _str(row[13])
            naturalidade = _str(row[9])

            if not nome or not cpf:
                erros += 1
                continue

            # date → datetime (meia-noite)
            nascimento = _datetime(row[8])
            data_coleta = _datetime(row[3])
            if nascimento is None or data_coleta is None:
                erros += 1
                continue

            finalidade = _str(row[28])
            if finalidade not in ('LEI', 'DJ'):
                finalidade = 'LEI'

            uf = _str(row[19])
            ufs_validas = {
                'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS',
                'MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR',
                'SC','SP','SE','TO',
            }
            if uf and uf.upper() not in ufs_validas:
                uf = None

            obj = DNA(
                cpf=cpf,
                data_da_coleta=data_coleta,
                gemeo=_simNao(row[5]),
                lacres=_str(row[6]),
                mae=mae or '',
                nascimento=nascimento,
                naturalidade=naturalidade or '',
                nome=nome,
                notas=_str(row[11]),
                pai=_str(row[12]),
                rg=rg or '',
                testemunha=_str(row[14]),
                testemunha2=_str(row[15]),
                tipo_penal=_str(row[16]),
                transfusao=_simNao(row[17]),
                transplante=_simNao(row[18]),
                uf=uf,
                unidade_prisional=_str(row[20]),
                nome_foto=_str(row[25]),
                vestigio=vestigio_map.get(row[26]),
                codigo_barras=_str(row[27]),
                finalidade_coleta=finalidade,
                num_processo_sei=_str(row[29]),
                ocorrencia=_str(row[30]),
                pais=_str(row[31]),
                processo_judicial=_str(row[32]),
                processado_banco_perfis_genetico='NO',
                estrangeiro=False,
                situacao=DNA.Situacao.NAO_APENADO,
                registrado_por_usuario_externo=False,
            )
            obj.save()
            criados += 1
        except Exception as e:
            erros += 1
            stdout.write(f'  [WARN] DNA id={row[0]}: {e}')

    stdout.write(f'  DNAs: {criados} criados, {erros} erros')


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Migra dados do dump MySQL do SPR-Custódia para o PostgreSQL'

    # Sequências a corrigir: (nome_sequência, nome_tabela)
    SEQUENCES = [
        ('cargos_cargo_id_seq',                                    'cargos_cargo'),
        ('autoridades_autoridade_id_seq',                          'autoridades_autoridade'),
        ('servicos_periciais_servicopericial_id_seq',              'servicos_periciais_servicopericial'),
        ('unidades_demandantes_unidadedemandante_id_seq',          'unidades_demandantes_unidadedemandante'),
        ('cidades_cidade_id_seq',                                  'cidades_cidade'),
        ('custodia_vestigio_id_seq',                               'custodia_vestigio'),
        ('custodia_vestigiomovimentacao_id_seq',                   'custodia_vestigiomovimentacao'),
        ('custodia_dna_id_seq',                                    'custodia_dna'),
        ('custodia_procedimentocustodia_id_seq',                   'custodia_procedimentocustodia'),
    ]

    def _resetar_sequences(self):
        """
        Corrige sequences PostgreSQL dessincronizadas.
        Sequences não são transacionais — o setval é permanente mesmo se
        a transação de dados for revertida depois.
        """
        from django.db import connection
        with connection.cursor() as cursor:
            for seq, tabela in self.SEQUENCES:
                sql = (
                    f"SELECT setval('{seq}', "
                    f"COALESCE((SELECT MAX(id) FROM {tabela}), 0) + 1, false)"
                )
                try:
                    cursor.execute(sql)
                except Exception as e:
                    self.stdout.write(f'  [WARN] sequence {seq}: {e}')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dump',
            default=DUMP_PADRAO,
            help='Caminho para o arquivo .sql do dump MySQL',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a migração sem gravar nada no banco',
        )
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Apaga todos os dados de custódia (Vestigio, VestigioMovimentacao, DNA) antes de re-importar',
        )

    def handle(self, *args, **options):
        dump_path = options['dump']
        dry_run = options['dry_run']

        self.stdout.write(f'Lendo dump: {dump_path}')
        tabelas = extrair_tabelas(dump_path)
        self.stdout.write(
            f'Tabelas encontradas: {", ".join(sorted(tabelas.keys()))}'
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — nenhum dado será gravado.'))
            for nome, linhas in tabelas.items():
                self.stdout.write(f'  {nome}: {len(linhas)} linhas')
            return

        if options['limpar']:
            self.stdout.write(self.style.WARNING('Limpando dados de custódia existentes...'))
            from custodia.models import DNA, VestigioMovimentacao, Vestigio
            DNA.all_objects.all().delete()
            VestigioMovimentacao.all_objects.all().delete()
            Vestigio.all_objects.all().delete()
            self.stdout.write('  DNA, VestigioMovimentacao, Vestigio removidos.')

        self.stdout.write('Corrigindo sequences PostgreSQL...')
        self._resetar_sequences()

        self.stdout.write('Mapeando usuarios Java -> Django (por CPF)...')
        user_map = construir_mapa_usuarios(tabelas)
        casados = sum(1 for u, _ in user_map.values() if u is not None)
        self.stdout.write(
            f'  {len(user_map)} usuários no dump, '
            f'{casados} encontrados no Django, '
            f'{len(user_map) - casados} sem correspondência (usarão nome de fallback)'
        )

        self.stdout.write('Iniciando migração (transação única)...')
        try:
            with transaction.atomic():
                migrar_municipios(tabelas.get('municipios', []), self.stdout)

                cargo_map = migrar_cargos(
                    tabelas.get('cargos', []), self.stdout
                )
                servico_map = migrar_servicos(
                    tabelas.get('servicos_peciricais', []), self.stdout
                )
                autoridade_map = migrar_autoridades(
                    tabelas.get('autoridades', []), cargo_map, self.stdout
                )
                unidade_map = migrar_unidades(
                    tabelas.get('unidades_demandantes', []), self.stdout
                )
                vestigio_map = migrar_vestigios(
                    tabelas.get('vestigios', []),
                    unidade_map, servico_map, autoridade_map,
                    user_map, self.stdout,
                )
                migrar_movimentacoes(
                    tabelas.get('vestigios_movimentacoes', []),
                    vestigio_map, unidade_map, servico_map, autoridade_map,
                    user_map, self.stdout,
                )
                migrar_dnas(
                    tabelas.get('dnas', []), vestigio_map, self.stdout
                )

            self.stdout.write(self.style.SUCCESS('Migração concluída com sucesso.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro — transação revertida: {e}'))
            raise
