import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spr.settings')
django.setup()

from IA.ai_service import LaudoAIService

print("="*60)
print("🧪 TESTE DO SERVIÇO DE IA")
print("="*60)

try:
    print("\n🔧 Criando serviço...")
    ai_service = LaudoAIService()
    print("✅ Serviço criado!")
    
    print("\n🔧 Testando gerar_resposta...")
    resposta = ai_service.gerar_resposta(
        pergunta="Delegado João Silva",
        tipo_laudo="GERAL",
        contexto_chat=[{"role": "user", "content": "Delegado João Silva"}]
    )
    
    print("\n✅ SUCESSO!")
    print(f"📝 RESPOSTA: {resposta}")
    
except Exception as e:
    print("\n❌ ERRO ENCONTRADO!")
    print(f"📛 Tipo: {type(e).__name__}")
    print(f"💬 Mensagem: {str(e)}")
    
    import traceback
    print("\n📋 TRACEBACK COMPLETO:")
    traceback.print_exc()

print("\n" + "="*60)