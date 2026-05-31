# custodia/management/commands/normalizar_auxiliares.py
#
# Corrige encoding e consolida duplicatas nas tabelas auxiliares que foram
# importadas múltiplas vezes (pré-ETL via SQL direto + ETL run 1 + ETL run 2).
#
# Uso:
#   python manage.py normalizar_auxiliares            ← dry-run (mostra o plano)
#   python manage.py normalizar_auxiliares --executar ← aplica tudo

import unicodedata
from django.core.management.base import BaseCommand
from django.db import transaction


# --- Utilitários --------------------------------------------------------------

def fix_encoding(s: str) -> str:
    """Corrige duplo encoding: bytes UTF-8 lidos como latin-1 -> unicode correto."""
    if not s:
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def remover_acentos(s: str) -> str:
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_nome(nome: str) -> str:
    """Normaliza para comparação: sem acento, sem prefixo 'SIGLA - ', uppercase."""
    n = fix_encoding(nome).strip().upper()
    # Remove prefixo tipo "1º DP - " ou "DAT - "
    if ' - ' in n:
        partes = n.split(' - ', 1)
        # Se a parte esquerda é curta (sigla), remove-a
        if len(partes[0]) <= 15:
            n = partes[1].strip()
    return remover_acentos(n)


def has_encoding_issue(s: str) -> bool:
    """Detecta se a string tem bytes de encoding duplo visíveis (Â, Ã seguidos de char)."""
    if not s:
        return False
    fixed = fix_encoding(s)
    return fixed != s or '�' in s


# --- Lógica por tabela --------------------------------------------------------

def normalizar_cargos(executar: bool, stdout):
    from cargos.models import Cargo

    todos = list(Cargo.all_objects.all())
    corrigidos = 0
    removidos = 0

    grupos: dict[str, list[Cargo]] = {}
    for c in todos:
        chave = remover_acentos(fix_encoding(c.nome).strip().upper())
        grupos.setdefault(chave, []).append(c)

    for chave, grupo in grupos.items():
        if len(grupo) == 1:
            c = grupo[0]
            nome_correto = fix_encoding(c.nome).strip().upper()
            if nome_correto != c.nome:
                stdout.write(f'  [CARGO] Corrigir: {c.nome!r} -> {nome_correto!r}')
                if executar:
                    Cargo.all_objects.filter(pk=c.pk).update(nome=nome_correto)
                corrigidos += 1
            continue

        # Duplicatas: mantém o mais antigo, deleta os outros
        grupo.sort(key=lambda x: x.created_at or x.pk)
        mestre = grupo[0]
        nome_correto = _melhor_nome(grupo)
        stdout.write(f'  [CARGO] Mestre id={mestre.id} -> {nome_correto!r}  ({len(grupo)-1} duplicatas)')

        if executar:
            # Apaga dups PRIMEIRO para liberar o nome único, depois renomeia o mestre
            for dup in grupo[1:]:
                dup.delete()
            Cargo.all_objects.filter(pk=mestre.pk).update(nome=nome_correto)

        for dup in grupo[1:]:
            stdout.write(f'           -> Apagar id={dup.id}')
            removidos += 1

    stdout.write(f'  Cargos: {corrigidos} nomes corrigidos, {removidos} duplicatas removidas')


def normalizar_unidades(executar: bool, stdout):
    from unidades_demandantes.models import UnidadeDemandante
    from custodia.models import Vestigio

    todos = list(UnidadeDemandante.all_objects.all())
    grupos: dict[str, list[UnidadeDemandante]] = {}
    for u in todos:
        chave = normalizar_nome(u.nome)
        grupos.setdefault(chave, []).append(u)

    corrigidos = 0
    removidos = 0
    fks_atualizadas = 0

    for chave, grupo in grupos.items():
        if len(grupo) == 1:
            u = grupo[0]
            nome_correto = fix_encoding(u.nome).strip().upper()
            sigla_correta = fix_encoding(u.sigla).strip().upper()
            if nome_correto != u.nome or sigla_correta != u.sigla:
                stdout.write(f'  [UNIDADE] Corrigir: {u.nome!r} -> {nome_correto!r}')
                if executar:
                    UnidadeDemandante.all_objects.filter(pk=u.pk).update(
                        nome=nome_correto, sigla=sigla_correta[:20]
                    )
                corrigidos += 1
            continue

        # Duplicatas: escolhe o mestre
        # Preferência: tem vestígios > mais antigo > nome mais completo
        def prioridade(u):
            refs = Vestigio.objects.filter(unidade_demandante=u).count()
            return (-(refs > 0), u.created_at or u.pk)

        grupo.sort(key=prioridade)
        mestre = grupo[0]

        # Nome mais completo entre os do grupo
        melhor_nome = max(
            (fix_encoding(u.nome) for u in grupo),
            key=lambda n: (len(n), n)
        ).strip().upper()
        melhor_sigla = fix_encoding(mestre.sigla).strip().upper()[:20]

        refs_total = sum(Vestigio.objects.filter(unidade_demandante=u).count() for u in grupo)
        stdout.write(
            f'  [UNIDADE] Mestre id={mestre.id} sigla={melhor_sigla!r} '
            f'{melhor_nome[:50]!r}  ({len(grupo)-1} dup, {refs_total} vestígios)'
        )

        from ocorrencias.models import Ocorrencia
        from ordens_servico.models import OrdemServico
        from usuarios.models import User as UsuarioModel
        mestre_pk = mestre.pk

        for dup in grupo[1:]:
            dup_pk = dup.pk
            refs = Vestigio.objects.filter(unidade_demandante_id=dup_pk).count()
            stdout.write(f'           -> Migrar id={dup_pk} ({refs} vest.) -> mestre')
            fks_atualizadas += refs
            removidos += 1
            if executar:
                Vestigio.all_objects.filter(unidade_demandante_id=dup_pk).update(
                    unidade_demandante_id=mestre_pk
                )
                Ocorrencia.all_objects.filter(unidade_demandante_id=dup_pk).update(
                    unidade_demandante_id=mestre_pk
                )
                OrdemServico.all_objects.filter(unidade_demandante_id=dup_pk).update(
                    unidade_demandante_id=mestre_pk
                )
                UsuarioModel.objects.filter(unidade_demandante_id=dup_pk).update(
                    unidade_demandante_id=mestre_pk
                )
                dup.delete()

        if executar:
            UnidadeDemandante.all_objects.filter(pk=mestre_pk).update(
                nome=melhor_nome, sigla=melhor_sigla
            )

    stdout.write(
        f'  Unidades: {corrigidos} nomes corrigidos, {removidos} duplicatas removidas, '
        f'{fks_atualizadas} vestígios redirecionados'
    )


def _melhor_nome(grupo) -> str:
    """
    Escolhe o melhor nome entre os do grupo:
    1. Sem U+FFFD (replacement char) — descarta nomes com chars substituídos
    2. Sem artefatos 'Â' do encoding duplo latin-1
    3. Mais longo (mais completo)
    """
    def qualidade(nome):
        fixed = fix_encoding(nome).strip().upper()
        sem_fffd = '�' not in fixed
        sem_artifact = 'Â' not in fixed and '\xc2' not in fixed
        return (sem_fffd, sem_artifact, len(fixed), fixed)

    candidatos = [(fix_encoding(obj.nome).strip().upper(), obj) for obj in grupo]
    candidatos.sort(key=lambda x: qualidade(x[0]), reverse=True)
    return candidatos[0][0]


def normalizar_autoridades(executar: bool, stdout):
    from autoridades.models import Autoridade
    from custodia.models import Vestigio, VestigioMovimentacao

    todos = list(Autoridade.all_objects.all())
    grupos: dict[str, list[Autoridade]] = {}
    for a in todos:
        chave = remover_acentos(fix_encoding(a.nome).strip().upper())
        grupos.setdefault(chave, []).append(a)

    corrigidos = 0
    removidos = 0

    for chave, grupo in grupos.items():
        if len(grupo) == 1:
            a = grupo[0]
            nome_correto = fix_encoding(a.nome).strip().upper()
            if nome_correto != a.nome:
                stdout.write(f'  [AUTORID] Corrigir: {a.nome!r} -> {nome_correto!r}')
                if executar:
                    Autoridade.all_objects.filter(pk=a.pk).update(nome=nome_correto)
                corrigidos += 1
            continue

        # Mestre: prefere o mais antigo que tenha referências, depois mais antigo
        grupo.sort(key=lambda x: x.created_at or x.pk)
        mestre = grupo[0]
        # Nome: usa o melhor do grupo (sem artefatos, mais completo)
        nome_correto = _melhor_nome(grupo)

        stdout.write(f'  [AUTORID] Mestre id={mestre.id} -> {nome_correto!r}  ({len(grupo)-1} dup)')

        from ocorrencias.models import Ocorrencia
        mestre_pk = mestre.pk

        for dup in grupo[1:]:
            dup_pk = dup.pk
            stdout.write(f'           -> Apagar id={dup_pk}')
            removidos += 1
            if executar:
                Vestigio.all_objects.filter(autoridade_id=dup_pk).update(autoridade_id=mestre_pk)
                VestigioMovimentacao.all_objects.filter(autoridade_id=dup_pk).update(autoridade_id=mestre_pk)
                Ocorrencia.all_objects.filter(autoridade_id=dup_pk).update(autoridade_id=mestre_pk)
                dup.delete()

        if executar:
            Autoridade.all_objects.filter(pk=mestre_pk).update(nome=nome_correto)

    stdout.write(f'  Autoridades: {corrigidos} nomes corrigidos, {removidos} duplicatas removidas')


def normalizar_servicos(executar: bool, stdout):
    """Corrige encoding de servicos_periciais (sigla + nome). Sem dedup — são serviços distintos."""
    from servicos_periciais.models import ServicoPericial

    corrigidos = 0
    for s in ServicoPericial.all_objects.all():
        nome_ok  = fix_encoding(s.nome).strip().upper()[:50]
        sigla_ok = fix_encoding(s.sigla).strip().upper()[:10]
        if nome_ok != s.nome or sigla_ok != s.sigla:
            stdout.write(f'  [SERVICO] id={s.id} {s.sigla!r} {s.nome!r} -> {sigla_ok!r} {nome_ok!r}')
            if executar:
                ServicoPericial.all_objects.filter(pk=s.pk).update(nome=nome_ok, sigla=sigla_ok)
            corrigidos += 1
    stdout.write(f'  Servicos Periciais: {corrigidos} nomes corrigidos')


def normalizar_cidades(executar: bool, stdout):
    """Corrige encoding e consolida duplicatas em cidades.Cidade."""
    from cidades.models import Cidade, Bairro
    from ocorrencias.models import Ocorrencia

    todos = list(Cidade.all_objects.all())
    grupos: dict[str, list] = {}
    for c in todos:
        chave = remover_acentos(fix_encoding(c.nome).strip().upper())
        grupos.setdefault(chave, []).append(c)

    corrigidos = 0
    removidos = 0

    for chave, grupo in grupos.items():
        if len(grupo) == 1:
            c = grupo[0]
            nome_ok = fix_encoding(c.nome).strip().upper()
            if nome_ok != c.nome:
                stdout.write(f'  [CIDADE] Corrigir id={c.id}: {c.nome!r} -> {nome_ok!r}')
                if executar:
                    Cidade.all_objects.filter(pk=c.pk).update(nome=nome_ok)
                corrigidos += 1
            continue

        grupo.sort(key=lambda x: x.created_at or x.pk)
        mestre = grupo[0]
        nome_ok = _melhor_nome(grupo)
        mestre_pk = mestre.pk

        refs = sum(Ocorrencia.all_objects.filter(cidade_id=g.pk).count() for g in grupo)
        stdout.write(f'  [CIDADE] Mestre id={mestre_pk} -> {nome_ok!r}  ({len(grupo)-1} dup, {refs} ocorr.)')

        for dup in grupo[1:]:
            dup_pk = dup.pk
            stdout.write(f'           -> Apagar id={dup_pk}')
            removidos += 1
            if executar:
                Ocorrencia.all_objects.filter(cidade_id=dup_pk).update(cidade_id=mestre_pk)
                Bairro.all_objects.filter(cidade_id=dup_pk).update(cidade_id=mestre_pk)
                dup.delete()

        if executar:
            Cidade.all_objects.filter(pk=mestre_pk).update(nome=nome_ok)

    stdout.write(f'  Cidades: {corrigidos} nomes corrigidos, {removidos} duplicatas removidas')


# --- Command ------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Corrige encoding e consolida duplicatas nas tabelas auxiliares'

    def add_arguments(self, parser):
        parser.add_argument(
            '--executar',
            action='store_true',
            help='Aplica as alteracoes (padrao: apenas mostra o plano)',
        )

    def handle(self, *args, **options):
        executar = options['executar']

        if not executar:
            self.stdout.write(self.style.WARNING(
                'DRY RUN -- nenhuma alteracao sera feita. Use --executar para aplicar.'
            ))

        self.stdout.write('\n-- Cargos ------------------------------')
        normalizar_cargos(executar, self.stdout)

        self.stdout.write('\n-- Unidades Demandantes ----------------')
        normalizar_unidades(executar, self.stdout)

        self.stdout.write('\n-- Autoridades -------------------------')
        normalizar_autoridades(executar, self.stdout)

        self.stdout.write('\n-- Servicos Periciais ------------------')
        normalizar_servicos(executar, self.stdout)

        self.stdout.write('\n-- Cidades -----------------------------')
        normalizar_cidades(executar, self.stdout)

        if executar:
            self.stdout.write(self.style.SUCCESS('\nNormalizacao concluida.'))
        else:
            self.stdout.write(self.style.WARNING('\nDRY RUN finalizado. Rode com --executar para aplicar.'))


