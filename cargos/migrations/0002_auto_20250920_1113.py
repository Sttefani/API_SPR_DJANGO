# cargos/migrations/0002_auto_....py

from django.db import migrations
from collections import defaultdict


def convert_cargo_names_to_uppercase(apps, schema_editor):
    """
    Converte nomes de cargos para caixa alta e resolve duplicatas.
    """
    Cargo = apps.get_model('cargos', 'Cargo')
    db_alias = schema_editor.connection.alias

    cargos_agrupados = defaultdict(lambda: {'original': None, 'duplicados': []})

    for cargo in Cargo.objects.using(db_alias).all().order_by('id'):
        nome_upper = cargo.nome.upper()

        if cargos_agrupados[nome_upper]['original'] is None:
            cargos_agrupados[nome_upper]['original'] = cargo
        else:
            cargos_agrupados[nome_upper]['duplicados'].append(cargo.id)

    ids_para_deletar = []
    cargos_para_atualizar = []

    for nome_upper, data in cargos_agrupados.items():
        ids_para_deletar.extend(data['duplicados'])

        original = data['original']
        if original.nome != nome_upper:
            original.nome = nome_upper
            cargos_para_atualizar.append(original)

    if ids_para_deletar:
        Cargo.objects.using(db_alias).filter(id__in=ids_para_deletar).delete()

    if cargos_para_atualizar:
        Cargo.objects.using(db_alias).bulk_update(cargos_para_atualizar, ['nome'])


class Migration(migrations.Migration):
    dependencies = [
        ('cargos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(convert_cargo_names_to_uppercase),
    ]