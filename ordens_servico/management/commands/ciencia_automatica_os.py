"""
Aplica ciência automática por inércia nas Ordens de Serviço.

Regra (anti-malandragem): se o servidor não der ciência manual na OS em até
OrdemServico.PRAZO_CIENCIA_AUTOMATICA_DIAS dias desde a emissão, o sistema dá a
ciência no lugar dele — com data RETROATIVA ao fim do período de inércia, para
que a inércia não estenda o prazo.

Uso:
    python manage.py ciencia_automatica_os

Sugestão de agendamento (Windows — Agendador de Tarefas, 1x/dia):
    schtasks /Create /SC DAILY /ST 06:00 /TN "SPR Ciencia Automatica OS" ^
      /TR "\"C:\\dev\\projetos em producao\\api_spr_django\\venv\\Scripts\\python.exe\" \"C:\\dev\\projetos em producao\\api_spr_django\\manage.py\" ciencia_automatica_os"
"""

from django.core.management.base import BaseCommand

from ordens_servico.models import OrdemServico


class Command(BaseCommand):
    help = (
        "Aplica ciência automática por inércia nas OS em AGUARDANDO_CIENCIA há mais "
        "de PRAZO_CIENCIA_AUTOMATICA_DIAS dias desde a emissão."
    )

    def handle(self, *args, **options):
        total = OrdemServico.aplicar_ciencia_automatica_pendentes()
        if total:
            self.stdout.write(self.style.SUCCESS(
                f"Ciência automática aplicada em {total} ordem(ns) de serviço."
            ))
        else:
            self.stdout.write("Nenhuma OS pendente de ciência automática.")
