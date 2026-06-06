from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ocorrencias', '0001_initial'),
        ('protocolos', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='protocoloentrega',
            name='ocorrencia',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='protocolos_saida',
                to='ocorrencias.ocorrencia',
                verbose_name='Ocorrência',
            ),
        ),
    ]
