# cidades/migrations/0002_auto_....py (o nome do seu arquivo será diferente)

from django.db import migrations
from django.db.models.functions import Upper
from collections import defaultdict


def convert_cidade_names_to_uppercase(apps, schema_editor):
    """
    Converte nomes de cidades para caixa alta e resolve duplicatas.

    Lógica:
    1. Agrupa todas as cidades pelo seu nome em caixa alta.
    2. Para cada grupo, mantém o primeiro registro encontrado (o "original").
    3. Todos os outros registros do grupo (os "duplicados") são efetivamente
       removidos, e qualquer coisa que apontava para eles precisaria ser
       reatribuída (neste caso, não temos nada apontando para Cidade).
    4. Atualiza o nome do registro original para caixa alta.
    """
    Cidade = apps.get_model('cidades', 'Cidade')
    db_alias = schema_editor.connection.alias

    # Dicionário para guardar os originais e os IDs duplicados
    # Ex: {'BOA VISTA': {'original': obj_cidade_1, 'duplicados': [id2, id3]}}
    cidades_agrupadas = defaultdict(lambda: {'original': None, 'duplicados': []})

    # Usamos .all_objects para garantir que pegamos até os soft-deleted
    for cidade in Cidade.objects.using(db_alias).all().order_by('id'):
        nome_upper = cidade.nome.upper()

        if cidades_agrupadas[nome_upper]['original'] is None:
            # Primeiro que encontramos com este nome, ele é o original
            cidades_agrupadas[nome_upper]['original'] = cidade
        else:
            # Já temos um original, então este é um duplicado
            cidades_agrupadas[nome_upper]['duplicados'].append(cidade.id)

    ids_para_deletar = []
    cidades_para_atualizar = []

    for nome_upper, data in cidades_agrupadas.items():
        # Adiciona todos os IDs duplicados à lista de deleção
        ids_para_deletar.extend(data['duplicados'])

        # Pega o objeto original e atualiza seu nome, se necessário
        original = data['original']
        if original.nome != nome_upper:
            original.nome = nome_upper
            cidades_para_atualizar.append(original)

    # Deleta todos os duplicados de uma vez
    if ids_para_deletar:
        Cidade.objects.using(db_alias).filter(id__in=ids_para_deletar).delete()

    # Atualiza todos os originais de uma vez
    if cidades_para_atualizar:
        Cidade.objects.using(db_alias).bulk_update(cidades_para_atualizar, ['nome'])


class Migration(migrations.Migration):
    dependencies = [
        ('cidades', '0001_initial'),  # Depende da migração que criou a tabela
    ]

    operations = [
        # Executa nossa função Python customizada
        migrations.RunPython(convert_cidade_names_to_uppercase),
    ]