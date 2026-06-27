import django.db.models.deletion
from django.db import migrations, models


def backfill_origem(apps, schema_editor):
    """
    Backfill honesto do serviço de origem:

    - Vestígios SEM movimentação interna aceita ainda têm `servico_pericial`
      igual ao serviço de cadastro → origem intacta, copiamos.
    - Vestígios COM movimentação interna já aceita tiveram `servico_pericial`
      sobrescrito no passado (aceitar() antigo) → a origem real foi perdida e
      NÃO há histórico para recuperá-la. Deixamos `servico_pericial_origem`
      como NULL ("não registrada — dado histórico") em vez de inventar.
    """
    Vestigio = apps.get_model('custodia', 'Vestigio')
    VestigioMovimentacao = apps.get_model('custodia', 'VestigioMovimentacao')

    # Vestígios cuja origem foi sobrescrita: tiveram movimentação INTERNA aceita
    # (mov com servico_pericial preenchido e aceito=True).
    movidos = set(
        VestigioMovimentacao.objects
        .filter(aceito=True, servico_pericial__isnull=False)
        .values_list('vestigio_id', flat=True)
    )

    qs = Vestigio.objects.filter(
        servico_pericial_origem__isnull=True,
        servico_pericial__isnull=False,
    )
    for v in qs.iterator():
        if v.id in movidos:
            continue  # origem perdida — mantém NULL (honesto)
        v.servico_pericial_origem_id = v.servico_pericial_id
        v.save(update_fields=['servico_pericial_origem'])


class Migration(migrations.Migration):

    dependencies = [
        ('servicos_periciais', '0001_initial'),
        ('custodia', '0009_fichavestigioregistro_conteudo_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='vestigio',
            name='servico_pericial_origem',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vestigios_origem',
                to='servicos_periciais.servicopericial',
            ),
        ),
        migrations.RunPython(backfill_origem, migrations.RunPython.noop),
    ]
