import chromadb
from sentence_transformers import SentenceTransformer
import PyPDF2
from django.conf import settings
import os


class LaudoRAGService:
    """Serviço para indexar e buscar laudos usando RAG"""
    
    def __init__(self):
        # ChromaDB (banco vetorial)
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_or_create_collection(name="laudos")
        
        # Modelo de embeddings (converte texto em vetores)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def extrair_texto_pdf(self, pdf_path):
        """Extrai texto de um PDF"""
        texto = ""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    texto += page.extract_text() + "\n"
        except Exception as e:
            print(f"❌ Erro ao ler PDF: {e}")
        return texto
    
    def dividir_em_chunks(self, texto, tamanho=500):
        """Divide texto em pedaços menores"""
        palavras = texto.split()
        chunks = []
        for i in range(0, len(palavras), tamanho):
            chunk = ' '.join(palavras[i:i+tamanho])
            chunks.append(chunk)
        return chunks
    
    def indexar_laudo(self, laudo_id, pdf_path, tipo_exame):
        """Indexa um laudo no banco vetorial"""
        # 1. Extrai texto do PDF
        texto = self.extrair_texto_pdf(pdf_path)
        
        # 2. Divide em chunks
        chunks = self.dividir_em_chunks(texto)
        
        # 3. Gera embeddings
        embeddings = self.model.encode(chunks).tolist()
        
        # 4. Salva no ChromaDB
        ids = [f"{laudo_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"laudo_id": laudo_id, "tipo_exame": tipo_exame} for _ in chunks]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        
        return len(chunks)
    
    def buscar_similares(self, pergunta, tipo_exame=None, n_results=3):
        """Busca laudos similares à pergunta"""
        # Gera embedding da pergunta
        query_embedding = self.model.encode([pergunta]).tolist()
        
        # Busca no ChromaDB
        where_filter = {"tipo_exame": tipo_exame} if tipo_exame else None
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where_filter
        )
        
        return results['documents'][0] if results['documents'] else []