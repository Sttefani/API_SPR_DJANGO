# ocorrencias/management/commands/migrar_bairros.py

from django.core.management.base import BaseCommand
from django.db import transaction
from ocorrencias.endereco_models import EnderecoOcorrencia
from cidades.models import Bairro, Cidade


class Command(BaseCommand):
    help = "Migra bairros do campo texto (bairro_legado) para a tabela normalizada (Bairro)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra o que seria feito, sem executar",
        )

    def normalize_bairro_name(self, nome):
        """Normaliza o nome do bairro para comparação"""
        if not nome:
            return ""
        # Remove espaços extras, converte para maiúsculo
        return " ".join(nome.upper().split())

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "=== MODO DRY-RUN (nenhuma alteração será feita) ===\n"
                )
            )

        # AJUSTE: Busca endereços onde o 'bairro_novo' ainda está vazio
        enderecos = (
            EnderecoOcorrencia.objects.filter(bairro_novo__isnull=True)
            .exclude(bairro_legado__isnull=True)
            .exclude(bairro_legado="")
            .select_related("ocorrencia__cidade")
        )

        total = enderecos.count()
        self.stdout.write(f"Encontrados {total} endereços para processar\n")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nenhum endereço para migrar!"))
            return

        # Agrupa por cidade e bairro para análise
        analise = {}
        for endereco in enderecos:
            cidade = endereco.ocorrencia.cidade if endereco.ocorrencia else None
            if not cidade:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ Endereço ID {endereco.id} sem cidade vinculada - IGNORADO"
                    )
                )
                continue

            bairro_normalizado = self.normalize_bairro_name(endereco.bairro_legado)

            if cidade.id not in analise:
                analise[cidade.id] = {"cidade": cidade, "bairros": {}}

            if bairro_normalizado not in analise[cidade.id]["bairros"]:
                analise[cidade.id]["bairros"][bairro_normalizado] = {
                    "variacoes": set(),
                    "enderecos": [],
                }

            analise[cidade.id]["bairros"][bairro_normalizado]["variacoes"].add(
                endereco.bairro_legado
            )
            analise[cidade.id]["bairros"][bairro_normalizado]["enderecos"].append(
                endereco
            )

        # Mostra análise
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("ANÁLISE DE BAIRROS POR CIDADE")
        self.stdout.write("=" * 60 + "\n")

        for cidade_id, dados in analise.items():
            cidade = dados["cidade"]
            self.stdout.write(f"\n📍 {cidade.nome}:")

            for bairro_norm, info in dados["bairros"].items():
                variacoes = info["variacoes"]
                qtd = len(info["enderecos"])

                if len(variacoes) > 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f'   ⚠️ "{bairro_norm}" ({qtd} registros) - VARIAÇÕES: {variacoes}'
                        )
                    )
                else:
                    self.stdout.write(f'   ✓ "{bairro_norm}" ({qtd} registros)')

        if dry_run:
            self.stdout.write("\n" + self.style.WARNING("=== FIM DO DRY-RUN ==="))
            self.stdout.write("Execute sem --dry-run para aplicar as alterações.")
            return

        # Executa a migração
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("EXECUTANDO MIGRAÇÃO")
        self.stdout.write("=" * 60 + "\n")

        criados = 0
        atualizados = 0
        erros = 0

        with transaction.atomic():
            for cidade_id, dados in analise.items():
                cidade = dados["cidade"]

                for bairro_norm, info in dados["bairros"].items():
                    # Cria ou busca o bairro normalizado
                    bairro_obj, created = Bairro.objects.get_or_create(
                        nome=bairro_norm, cidade=cidade
                    )

                    if created:
                        criados += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'   ✓ Criado bairro: "{bairro_norm}" em {cidade.nome}'
                            )
                        )

                    # Atualiza os endereços
                    for endereco in info["enderecos"]:
                        try:
                            # AJUSTE: Grava no campo 'bairro_novo'
                            endereco.bairro_novo = bairro_obj
                            endereco.save(update_fields=["bairro_novo", "updated_at"])
                            atualizados += 1
                        except Exception as e:
                            erros += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f"   ❌ Erro ao atualizar endereço ID {endereco.id}: {e}"
                                )
                            )

        # Resumo final
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("RESUMO DA MIGRAÇÃO")
        self.stdout.write("=" * 60)
        self.stdout.write(f"  Bairros criados: {criados}")
        self.stdout.write(f"  Endereços atualizados: {atualizados}")
        self.stdout.write(f"  Erros: {erros}")
        self.stdout.write("=" * 60 + "\n")

        if erros == 0:
            self.stdout.write(self.style.SUCCESS("✅ Migração concluída com sucesso!"))
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠️ Migração concluída com {erros} erros.")
            )
