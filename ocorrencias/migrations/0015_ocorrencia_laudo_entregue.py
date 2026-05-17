from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ocorrencias", "0014_ocorrencia_exames_solicitados"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="ocorrencia",
            name="data_laudo_entregue",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Data de Entrega do Laudo"
            ),
        ),
        migrations.AddField(
            model_name="ocorrencia",
            name="laudo_entregue_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocorrencias_laudo_entregue",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Laudo entregue por",
            ),
        ),
        migrations.AlterField(
            model_name="ocorrencia",
            name="status",
            field=models.CharField(
                choices=[
                    ("AGUARDANDO_PERITO", "Aguardando Atribuição de Perito"),
                    ("EM_ANALISE", "Em Análise"),
                    ("LAUDO_ENTREGUE", "Laudo Entregue"),
                    ("FINALIZADA", "Finalizada"),
                ],
                default="AGUARDANDO_PERITO",
                max_length=20,
                verbose_name="Status da Ocorrência",
            ),
        ),
    ]
