from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('custodia', '0006_add_motivo_finalizacao_vestigio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CertidaoRegistro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('protocolo', models.CharField(db_index=True, max_length=16, unique=True)),
                ('tipo', models.CharField(
                    choices=[('CERTIDAO', 'Certidão de Ausência'), ('COMPROVANTE', 'Comprovante de Consulta')],
                    max_length=20,
                )),
                ('nome_consultado', models.CharField(blank=True, max_length=255)),
                ('cpf_consultado',  models.CharField(blank=True, max_length=20)),
                ('rg_consultado',   models.CharField(blank=True, max_length=30)),
                ('emitido_por_nome', models.CharField(max_length=255)),
                ('emitido_em', models.DateTimeField()),
                ('emitido_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='certidoes_emitidas',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Certidão de Ausência',
                'verbose_name_plural': 'Certidões de Ausência',
                'ordering': ['-emitido_em'],
            },
        ),
    ]
