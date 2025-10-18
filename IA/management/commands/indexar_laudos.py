from django.core.management.base import BaseCommand
from IA.models import LaudoReferencia
from IA.rag_service import LaudoRAGService

class Command(BaseCommand):
    help = 'Indexa laudos no banco vetorial (ChromaDB)'

    def add_arguments(self, parser):
        parser.add_argument('--forcar', action='store_true', help='Reindexar todos')

    def handle(self, *args, **options):
        forcar = options['forcar']
        
        # Filtra laudos não processados
        if forcar:
            laudos = LaudoReferencia.objects.all()
        else:
            laudos = LaudoReferencia.objects.filter(processado=False)
        
        total = laudos.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('⚠️  Nenhum laudo para processar'))
            return
        
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('🧠 INDEXAÇÃO DE LAUDOS (Vetorização)'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'📚 Total a processar: {total} laudos')
        self.stdout.write('⏳ Isso pode demorar alguns minutos...')
        self.stdout.write('=' * 60)
        
        # Inicializa serviço RAG
        self.stdout.write('\n📥 Carregando modelo de embeddings...')
        rag = LaudoRAGService()
        self.stdout.write(self.style.SUCCESS('✅ Modelo carregado!\n'))
        
        sucesso = 0
        falhas = 0
        
        for i, laudo in enumerate(laudos, 1):
            self.stdout.write(f'[{i}/{total}] {laudo.titulo}...')
            
            try:
                # Indexa no ChromaDB
                pdf_path = laudo.arquivo_pdf.path
                chunks = rag.indexar_laudo(laudo.id, pdf_path, laudo.tipo_exame)
                
                self.stdout.write(self.style.SUCCESS(f'🔢 Gerando embeddings para {chunks} chunks...'))
                self.stdout.write(self.style.SUCCESS(f'✅ Indexado: {laudo.titulo} ({chunks} chunks)'))
                
                # Marca como processado
                laudo.processado = True
                laudo.save()
                
                sucesso += 1
                self.stdout.write(self.style.SUCCESS('   ✅ Sucesso\n'))
                
            except Exception as e:
                falhas += 1
                self.stdout.write(self.style.ERROR(f'   ❌ ERRO: {str(e)}\n'))
        
        # Resumo final
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📊 RESUMO'))
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS(f'✅ Sucesso: {sucesso}'))
        if falhas > 0:
            self.stdout.write(self.style.ERROR(f'❌ Falhas: {falhas}'))
        self.stdout.write(f'📊 Total: {total}')
        self.stdout.write('=' * 60)
        
        if sucesso > 0:
            self.stdout.write(self.style.SUCCESS('\n🎉 Banco vetorial pronto para uso!'))
            self.stdout.write(self.style.SUCCESS('🚀 Agora você pode testar o chat com a IA\n'))