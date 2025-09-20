# servicos_periciais/migrations/0002_auto_....py

from django.db import migrations
from collections import defaultdict


def convert_servico_names_to_uppercase(apps, schema_editor):
    """
    Converte nomes de serviços periciais para caixa alta e resolve duplicatas.
    """
    ServicoPericial = apps.get_model('servicos_periciais', 'ServicoPericial')
    db_alias = schema_editor.connection.alias

    servicos_agrupados = defaultdict(lambda: {'original': None, 'duplicados': []})

    for servico in ServicoPericial.objects.using(db_alias).all().order_by('id'):
        nome_upper = servico.nome.upper()

        if servicos_agrupados[nome_upper]['original'] is None:
            servicos_agrupados[nome_upper]['original'] = servico
        else:
            servicos_agrupados[nome_upper]['duplicados'].append(servico.id)

    ids_para_deletar = []
    servicos_para_atualizar = []

    for nome_upper, data in servicos_agrupados.items():
        ids_para_deletar.extend(data['duplicados'])

        original = data['original']
        if original.nome != nome_upper:
            original.nome = nome_upper
            servicos_para_atualizar.append(original)

    if ids_para_deletar:
        ServicoPericial.objects.using(db_alias).filter(id__in=ids_para_deletar).delete()

    if servicos_para_atualizar:
        ServicoPericial.objects.using(db_alias).bulk_update(servicos_para_atualizar, ['nome'])


class Migration(migrations.Migration):
    dependencies = [
        ('servicos_periciais', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(convert_servico_names_to_uppercase),
    ]