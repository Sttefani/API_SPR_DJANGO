from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from .ai_service import LaudoAIService
import uuid

# Instância global do serviço de IA
ai_service = LaudoAIService()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def iniciar_sessao(request):
    """
    Inicia uma nova sessão de chat
    
    Body: { "tipo_laudo": "GERAL" }
    """
    tipo_laudo = request.data.get('tipo_laudo', 'GERAL')
    
    # Gera chave única para a sessão
    session_key = f"chat_{uuid.uuid4().hex}"
    
    # Armazena dados da sessão no cache (Redis/Memory)
    session_data = {
        'tipo_laudo': tipo_laudo,
        'historico': [],
        'dados_coletados': {}
    }
    
    cache.set(session_key, session_data, timeout=3600)  # 1 hora
    
    # Mensagem inicial da IA
    mensagem_inicial = ai_service.gerar_resposta(
        pergunta="Iniciar conversa",
        tipo_laudo=tipo_laudo,
        contexto_chat=[]
    )
    
    # Adiciona ao histórico
    session_data['historico'].append({
        'role': 'assistant',
        'content': mensagem_inicial
    })
    cache.set(session_key, session_data, timeout=3600)
    
    return Response({
        'session_key': session_key,
        'mensagem_inicial': mensagem_inicial,
        'tipo_laudo': tipo_laudo
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_mensagem(request):
    """
    Envia mensagem para a IA
    
    Body: { "session_key": "...", "mensagem": "..." }
    """
    session_key = request.data.get('session_key')
    mensagem_usuario = request.data.get('mensagem')
    
    if not session_key or not mensagem_usuario:
        return Response(
            {'erro': 'session_key e mensagem são obrigatórios'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Recupera sessão
    session_data = cache.get(session_key)
    if not session_data:
        return Response(
            {'erro': 'Sessão inválida ou expirada'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Adiciona mensagem do usuário ao histórico
    session_data['historico'].append({
        'role': 'user',
        'content': mensagem_usuario
    })
    
    # DEBUG
    print("\n" + "="*60)
    print("🔍 VIEWS.PY - ENVIAR_MENSAGEM")
    print(f"📝 Mensagem: {mensagem_usuario}")
    print(f"📊 Tipo Laudo: {session_data['tipo_laudo']}")
    print("="*60)
    
    # Gera resposta da IA usando RAG
    try:
        resposta_ia = ai_service.gerar_resposta(
            pergunta=mensagem_usuario,
            tipo_laudo=session_data['tipo_laudo'],
            contexto_chat=session_data['historico']
        )
        
        print(f"\n✅ RESPOSTA DA IA:")
        print(resposta_ia[:300])
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERRO AO GERAR RESPOSTA: {e}")
        print("="*60 + "\n")
        
        return Response(
            {'erro': f'Erro ao processar mensagem: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Adiciona resposta da IA ao histórico
    session_data['historico'].append({
        'role': 'assistant',
        'content': resposta_ia
    })
    
    # Atualiza cache
    cache.set(session_key, session_data, timeout=3600)
    
    return Response({
        'resposta': resposta_ia,
        'session_key': session_key
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obter_historico(request, session_key):
    """
    Obtém histórico da conversa
    
    GET /api/ia/chat/historico/{session_key}/
    """
    session_data = cache.get(session_key)
    
    if not session_data:
        return Response(
            {'erro': 'Sessão não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    return Response({
        'historico': session_data['historico'],
        'tipo_laudo': session_data['tipo_laudo']
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gerar_laudo(request):
    """
    Gera o laudo completo baseado na conversa
    
    Body: { "session_key": "..." }
    """
    session_key = request.data.get('session_key')
    
    if not session_key:
        return Response(
            {'erro': 'session_key é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    session_data = cache.get(session_key)
    if not session_data:
        return Response(
            {'erro': 'Sessão não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Formata histórico para string
    historico_texto = "\n\n".join([
        f"{'Usuário' if msg['role'] == 'user' else 'IA'}: {msg['content']}"
        for msg in session_data['historico']
    ])
    
    # Gera laudo completo
    try:
        laudo_completo = ai_service.gerar_laudo_completo(
            tipo_laudo=session_data['tipo_laudo'],
            dados_coletados={'historico': historico_texto}
        )
        
        return Response({
            'laudo': laudo_completo,
            'tipo_laudo': session_data['tipo_laudo']
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'erro': f'Erro ao gerar laudo: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )