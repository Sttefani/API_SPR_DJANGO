from django.core.management.base import BaseCommand
from ocorrencias.endereco_models import EnderecoOcorrencia
import time

class Command(BaseCommand):
    help = 'Geocodifica endereços externos sem coordenadas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite',
            type=int,
            default=None,
            help='Limitar número de endereços a processar (ex: --limite 5)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sem salvar no banco de dados'
        )

    def handle(self, *args, **options):
        limite = options.get('limite')
        dry_run = options.get('dry_run')
        
        # Buscar endereços sem coordenadas
        enderecos = EnderecoOcorrencia.objects.filter(
            tipo='EXTERNA',
            latitude__isnull=True
        ).select_related('ocorrencia', 'ocorrencia__cidade')
        
        if limite:
            enderecos = enderecos[:limite]
        
        total = enderecos.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ Todos os endereços já possuem coordenadas!\n'))
            return
        
        # Header
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.WARNING("📍 GEOCODIFICAÇÃO AUTOMÁTICA - RORAIMA"))
        self.stdout.write("="*70)
        self.stdout.write(f"📊 Encontrados {total} endereços para geocodificar")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 MODO SIMULAÇÃO (não vai salvar no banco)"))
        
        self.stdout.write("⏳ Iniciando processamento (aguarde, pode demorar)...")
        self.stdout.write("⚠️  Respeita limite de 1 req/segundo do OpenStreetMap\n")
        
        sucesso = 0
        falha = 0
        
        for i, endereco in enumerate(enderecos, 1):
            self.stdout.write(f"\n[{i}/{total}] Processando ID {endereco.id}:")
            self.stdout.write(f"   Ocorrência: {endereco.ocorrencia.numero_ocorrencia}")
            self.stdout.write(f"   Endereço: {endereco.logradouro or 'Sem logradouro'}")
            self.stdout.write(f"   Cidade: {endereco.ocorrencia.cidade.nome if endereco.ocorrencia.cidade else 'Sem cidade'}")
            
            # Chamar método de geocodificação
            resultado = endereco.geocodificar()
            
            if resultado:
                if not dry_run:
                    # Salvar no banco
                    endereco.save()
                    sucesso += 1
                    self.stdout.write(self.style.SUCCESS(f"   ✅ SALVO: {endereco.latitude}, {endereco.longitude}"))
                else:
                    sucesso += 1
                    self.stdout.write(self.style.SUCCESS(f"   ✅ ENCONTRADO (não salvo): {endereco.latitude}, {endereco.longitude}"))
            else:
                falha += 1
                self.stdout.write(self.style.WARNING(f"   ⚠️  NÃO ENCONTRADO"))
            
            # Respeitar rate limit do Nominatim (1 req/segundo)
            if i < total:
                self.stdout.write("   ⏱️  Aguardando 1.5s...")
                time.sleep(1.5)
        
        # Resumo final
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("📊 RESUMO DA GEOCODIFICAÇÃO"))
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS(f"✅ Sucesso: {sucesso} endereços"))
        self.stdout.write(self.style.WARNING(f"⚠️  Falhas: {falha} endereços"))
        self.stdout.write(f"📊 Total processado: {total}")
        
        if sucesso > 0:
            percentual = (sucesso / total) * 100
            self.stdout.write(self.style.SUCCESS(f"🎯 Taxa de sucesso: {percentual:.1f}%"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  MODO SIMULAÇÃO: Nada foi salvo no banco de dados"))
        
        self.stdout.write("="*70 + "\n")