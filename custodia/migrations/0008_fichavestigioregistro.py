from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('custodia', '0007_certidaoregistro'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FichaVestigioRegistro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('protocolo', models.CharField(db_index=True, max_length=16, unique=True)),
                ('vestigio_lacre', models.CharField(blank=True, max_length=255)),
                ('emitido_por_nome', models.CharField(max_length=255)),
                ('emitido_em', models.DateTimeField()),
                ('vestigio', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='fichas_emitidas',
                    to='custodia.vestigio',
                )),
                ('emitido_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='fichas_vestigio_emitidas',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Ficha de Acompanhamento Emitida',
                'verbose_name_plural': 'Fichas de Acompanhamento Emitidas',
                'ordering': ['-emitido_em'],
            },
        ),
    ]
