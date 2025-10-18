from django.core.management.base import BaseCommand
from IA.models import LaudoReferencia
from django.core.files import File
import os
from pathlib import Path

class Command(BaseCommand):
    help = 'Importa laudos em PDF de uma pasta do HD'

    def add_arguments(self, parser):
        parser.add_argument('pasta', type=str, help='Caminho da pasta com PDFs')
        parser.add_argument('--limite', type=int, default=None, help='Limite de arquivos')
        parser.add_argument('--ano', type=int, default=None, help='Filtrar por ano no nome')

    def handle(self, *args, **options):
        pasta = options['pasta']
        limite = options['limite']
        ano = options['ano']
        
        if not os.path.exists(pasta):
            self.stdout.write(self.style.ERROR(f'❌ Pasta não encontrada: {pasta}'))
            return
        
        self.stdout.write(self.style.SUCCESS('📂 Importando laudos...'))
        
        # Lista todos os PDFs
        pdfs = list(Path(pasta).rglob('*.pdf'))
        
        # Filtra por ano se especificado
        if ano:
            pdfs = [p for p in pdfs if str(ano) in p.name]
        
        # Limita quantidade
        if limite:
            pdfs = pdfs[:limite]
        
        total = 0
        ignorados = 0
        
        for pdf_path in pdfs:
            nome_arquivo = pdf_path.stem  # Nome sem extensão
            
            # Verifica se já existe
            if LaudoReferencia.objects.filter(titulo=nome_arquivo).exists():
                ignorados += 1
                continue
            
            # Tenta detectar tipo de exame pelo nome
            tipo_exame = "GERAL"
            nome_lower = nome_arquivo.lower()
            if 'thc' in nome_lower or 'droga' in nome_lower:
                tipo_exame = "THC"
            elif 'dna' in nome_lower:
                tipo_exame = "DNA"
            elif 'balistica' in nome_lower or 'arma' in nome_lower:
                tipo_exame = "BALÍSTICA"
            elif 'local' in nome_lower or 'crime' in nome_lower:
                tipo_exame = "LOCAL DE CRIME"
            
            # Cria registro
            with open(pdf_path, 'rb') as f:
                laudo = LaudoReferencia(
                    titulo=nome_arquivo,
                    tipo_exame=tipo_exame,
                    pasta_origem=str(pdf_path.parent)
                )
                laudo.arquivo_pdf.save(pdf_path.name, File(f), save=True)
            
            total += 1
            self.stdout.write(self.style.SUCCESS(f'✅ {nome_arquivo}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Total: {total} | Ignorados: {ignorados}'))
        self.stdout.write(self.style.WARNING('🔄 Rode agora: python manage.py indexar_laudos'))