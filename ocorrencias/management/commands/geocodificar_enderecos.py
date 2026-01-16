# ============================================
# ocorrencias/management/commands/geocodificar_enderecos.py
#
# VERSÃO MELHORADA COM FALLBACKS
# ============================================

from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Geocodifica endereços externos sem coordenadas (com fallbacks)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=None,
            help="Limitar número de endereços a processar (ex: --limite 5)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simular sem salvar no banco de dados",
        )
        parser.add_argument(
            "--id",
            type=int,
            default=None,
            help="Processar apenas um endereço específico pelo ID",
        )

    def handle(self, *args, **options):
        limite = options.get("limite")
        dry_run = options.get("dry_run")
        endereco_id = options.get("id")

        # Header
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.WARNING("📍 GEOCODIFICAÇÃO COM FALLBACKS - RORAIMA")
        )
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 MODO SIMULAÇÃO (não vai salvar no banco)")
            )

        # Importar a função auxiliar
        try:
            from ocorrencias.utils.geocoding import (
                geocodificar_com_fallback,
                reprocessar_enderecos_sem_coordenadas,
            )
        except ImportError:
            self.stdout.write(
                self.style.ERROR(
                    "\n❌ ERRO: Não foi possível importar o módulo de geocodificação."
                    "\n   Certifique-se de que o arquivo existe em:"
                    "\n   ocorrencias/utils/geocoding.py"
                    "\n   E que existe um __init__.py na pasta utils/"
                )
            )
            return

        # Processar um único endereço
        if endereco_id:
            self.processar_unico(endereco_id, dry_run, geocodificar_com_fallback)
            return

        # Processar múltiplos endereços
        self.stdout.write(f"⏳ Buscando endereços sem coordenadas...")

        estatisticas = reprocessar_enderecos_sem_coordenadas(
            limite=limite, dry_run=dry_run
        )

        # Exibir resumo
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("📊 RESUMO FINAL"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"📊 Total processado: {estatisticas['total']}")
        self.stdout.write(self.style.SUCCESS(f"✅ Sucesso: {estatisticas['sucesso']}"))
        self.stdout.write(self.style.WARNING(f"❌ Falha: {estatisticas['falha']}"))

        self.stdout.write("\n📍 Detalhamento por nível de precisão:")
        self.stdout.write(
            f"   Nível 1 (Endereço completo): {estatisticas['por_nivel'][1]}"
        )
        self.stdout.write(
            f"   Nível 2 (Bairro + Cidade):   {estatisticas['por_nivel'][2]}"
        )
        self.stdout.write(
            f"   Nível 3 (Sede município):    {estatisticas['por_nivel'][3]}"
        )

        if estatisticas["sucesso"] > 0 and estatisticas["total"] > 0:
            percentual = (estatisticas["sucesso"] / estatisticas["total"]) * 100
            self.stdout.write(
                self.style.SUCCESS(f"\n🎯 Taxa de sucesso: {percentual:.1f}%")
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  MODO SIMULAÇÃO: Nada foi salvo no banco de dados"
                )
            )

        self.stdout.write("=" * 70 + "\n")

    def processar_unico(self, endereco_id, dry_run, geocodificar_func):
        """Processa um único endereço pelo ID"""
        from ocorrencias.endereco_models import EnderecoOcorrencia

        try:
            endereco = EnderecoOcorrencia.objects.select_related(
                "ocorrencia", "ocorrencia__cidade", "bairro_novo"
            ).get(id=endereco_id)
        except EnderecoOcorrencia.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ Endereço ID {endereco_id} não encontrado!")
            )
            return

        self.stdout.write(f"\n📍 Processando endereço ID {endereco_id}:")
        self.stdout.write(f"   Ocorrência: {endereco.ocorrencia.numero_ocorrencia}")
        self.stdout.write(f"   Logradouro: {endereco.logradouro or '(vazio)'}")
        self.stdout.write(f"   Bairro: {endereco.nome_bairro or '(vazio)'}")

        if endereco.ocorrencia and endereco.ocorrencia.cidade:
            self.stdout.write(f"   Cidade: {endereco.ocorrencia.cidade.nome}")

        self.stdout.write(
            f"   Lat/Lng atual: {endereco.latitude}, {endereco.longitude}"
        )

        resultado = geocodificar_func(endereco, dry_run=dry_run)

        self.stdout.write("\n" + "-" * 50)
        if resultado["sucesso"]:
            self.stdout.write(self.style.SUCCESS(f"✅ SUCESSO!"))
            self.stdout.write(
                f"   Nível: {resultado['nivel']} ({resultado['nivel_nome']})"
            )
            self.stdout.write(
                f"   Coordenadas: [{resultado['latitude']}, {resultado['longitude']}]"
            )
            self.stdout.write(f"   Query usada: {resultado['query_usada']}")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("   ⚠️ DRY-RUN: Não salvo no banco")
                )
            else:
                self.stdout.write(self.style.SUCCESS("   💾 Salvo no banco de dados!"))
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ FALHA: Não foi possível geocodificar")
            )

        self.stdout.write("-" * 50 + "\n")
