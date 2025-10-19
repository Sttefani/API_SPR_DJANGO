import json
import os
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .ai_service import LaudoAIService
from .models import LaudoGerado, TemplateLaudo

# Instância global do serviço de IA
ai_service = LaudoAIService()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def iniciar_sessao(request):
    """
    Inicia uma nova sessão de chat
    """
    tipo_laudo = request.data.get("tipo_laudo", "GERAL")
    session_key = f"chat_{uuid.uuid4().hex}"
    session_data = {"tipo_laudo": tipo_laudo, "historico": [], "dados_coletados": {}}
    cache.set(session_key, session_data, timeout=3600)
    mensagem_inicial = ai_service.gerar_resposta(
        pergunta="Iniciar conversa", tipo_laudo=tipo_laudo, contexto_chat=[]
    )
    session_data["historico"].append({"role": "assistant", "content": mensagem_inicial})
    cache.set(session_key, session_data, timeout=3600)
    return Response(
        {
            "session_key": session_key,
            "mensagem_inicial": mensagem_inicial,
            "tipo_laudo": tipo_laudo,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enviar_mensagem(request):
    """
    Envia mensagem para a IA
    """
    session_key = request.data.get("session_key")
    mensagem_usuario = request.data.get("mensagem")
    if not session_key or not mensagem_usuario:
        return Response(
            {"erro": "session_key e mensagem são obrigatórios"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    session_data = cache.get(session_key)
    if not session_data:
        return Response(
            {"erro": "Sessão inválida ou expirada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    session_data["historico"].append({"role": "user", "content": mensagem_usuario})
    try:
        resposta_ia = ai_service.gerar_resposta(
            pergunta=mensagem_usuario,
            tipo_laudo=session_data["tipo_laudo"],
            contexto_chat=session_data["historico"],
        )
    except Exception as e:
        return Response(
            {"erro": f"Erro ao processar mensagem: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    session_data["historico"].append({"role": "assistant", "content": resposta_ia})
    cache.set(session_key, session_data, timeout=3600)
    return Response(
        {"resposta": resposta_ia, "session_key": session_key},
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def obter_historico(request, session_key):
    """
    Obtém histórico da conversa
    """
    session_data = cache.get(session_key)
    if not session_data:
        return Response(
            {"erro": "Sessão não encontrada"}, status=status.HTTP_404_NOT_FOUND
        )
    return Response(
        {"historico": session_data["historico"], "tipo_laudo": session_data["tipo_laudo"]},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def gerar_laudo(request):
    """
    Gera o laudo completo baseado na conversa
    """
    session_key = request.data.get("session_key")
    if not session_key:
        return Response(
            {"erro": "session_key é obrigatório"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    session_data = cache.get(session_key)
    if not session_data:
        return Response(
            {"erro": "Sessão não encontrada"}, status=status.HTTP_404_NOT_FOUND
        )
    historico_texto = "\n\n".join(
        [
            f"{'Usuário' if msg['role'] == 'user' else 'IA'}: {msg['content']}"
            for msg in session_data["historico"]
        ]
    )
    try:
        laudo_completo = ai_service.gerar_laudo_completo(
            tipo_laudo=session_data["tipo_laudo"],
            dados_coletados={"historico": historico_texto},
        )
        return Response(
            {
                "laudo": laudo_completo,
                "tipo_laudo": session_data["tipo_laudo"],
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"erro": f"Erro ao gerar laudo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ===============================================
# VIEWS PARA LAUDOS (Baseadas em Template)
# ===============================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def gerar_laudo_thc_view(request):
    """
    Gera laudo químico THC com base nos dados fornecidos
    """
    try:
        dados = request.data
        template = TemplateLaudo.objects.get(
            tipo="quimico_preliminar_thc", ativo=True
        )
        valido, faltantes, invalidos = template.validar_dados(dados)
        if not valido:
            return Response(
                {
                    "sucesso": False,
                    "status": "incompleto",
                    "campos_faltantes": faltantes,
                    "campos_invalidos": invalidos,
                    "mensagem": f"Campos faltantes: {', '.join(faltantes)}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        laudo_texto = template.preencher(dados)

        laudo_obj = LaudoGerado.objects.create(
            template=template,
            dados_preenchimento=dados,
            laudo_texto=laudo_texto,
            resultado=dados.get("resultado", ""),
            gerado_por=request.user,
        )
        return Response(
            {
                "sucesso": True,
                "laudo_id": laudo_obj.id,
                "laudo_texto": laudo_texto,
                "resultado": laudo_obj.resultado,
                "mensagem": "Laudo gerado com sucesso!",
            }
        )
    except TemplateLaudo.DoesNotExist:
        return Response(
            {"sucesso": False, "erro": "Template de laudo THC não encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()  # ← ADICIONAR ESTA LINHA
        print(f"❌ ERRO DETALHADO: {str(e)}")
        
        return Response(
            {"sucesso": False, "erro": f"Erro ao gerar laudo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(["GET"])
# A autenticação não é necessária para ver os campos do formulário
def obter_campos_laudo_thc(request):
    """
    Retorna os campos necessários para gerar laudo THC
    """
    try:
        template = TemplateLaudo.objects.get(
            tipo="quimico_preliminar_thc", ativo=True
        )
        campos_agrupados = {
            "identificacao": ["numero_laudo", "servico_pericial","nome_diretor", "nome_perito", "matricula_perito"],
            "requisicao": ["tipo_autoridade", "nome_autoridade", "numero_requisicao", "data_requisicao", "tipo_procedimento", "numero_procedimento"],
            "material": ["descricao_material", "massa_bruta_total", "lacres_entrada" ],
            "resultado": ["resultado", "peso_consumido", "peso_contraprova", "lacres_contraprova", "massa_liquida_final", "lacres_saida"],
            "finalizacao": ["nome_perito_assinatura"],
        }
        return Response(
            {
                "sucesso": True,
                "campos_obrigatorios": template.campos_obrigatorios,
                "campos_com_validacao": template.campos_com_validacao,
                "campos_automaticos": template.campos_automaticos,
                "campos_agrupados": campos_agrupados,
                "exemplo_dados": template.exemplo_dados,
            }
        )
    except TemplateLaudo.DoesNotExist:
        return Response(
            {"sucesso": False, "erro": "Template não encontrado"}, status=404
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def obter_laudo_gerado(request, laudo_id):
    """
    Retorna um laudo específico pelo ID
    """
    try:
        laudo = LaudoGerado.objects.get(id=laudo_id)
        
        # Determina o nome do gerador (usando nome_completo, não get_full_name)
        if laudo.gerado_por:
            nome_gerador = laudo.gerado_por.nome_completo or laudo.gerado_por.email or f'Usuário #{laudo.gerado_por.id}'
        else:
            nome_gerador = 'Sistema'
        
        return Response(
            {
                "sucesso": True,
                "laudo": {
                    "id": laudo.id,
                    "template_tipo": laudo.template.tipo,
                    "template_nome": laudo.template.nome,
                    "laudo_texto": laudo.laudo_texto,
                    "resultado": laudo.resultado,
                    "dados_preenchimento": laudo.dados_preenchimento,
                    "gerado_por": nome_gerador,
                    "gerado_em": laudo.gerado_em.isoformat(),
                    "pdf_url": laudo.pdf_arquivo.url if laudo.pdf_arquivo else None,
                },
            }
        )
    except LaudoGerado.DoesNotExist:
        return Response(
            {"sucesso": False, "erro": "Laudo não encontrado"}, status=404
        )
        
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gerar_laudo_pdf_view(request, laudo_id):
    """
    Gera um PDF para um laudo específico usando ReportLab.
    """
    try:
        laudo = LaudoGerado.objects.get(id=laudo_id)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="laudo_{laudo_id}.pdf"'

        doc = SimpleDocTemplate(response, rightMargin=0.7*inch, leftMargin=0.7*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)

        styles = getSampleStyleSheet()
        style_body = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            alignment=TA_JUSTIFY,
            fontSize=10,
            leading=14
        )
        
        story = []

        caminho_imagem = os.path.join(settings.BASE_DIR, 'IA', 'static', 'IA','images', 'logo_pcrr.jpg')
        logo = Image(caminho_imagem, width=1*inch, height=1.12*inch)
        logo.hAlign = 'CENTER'
        story.append(logo)
        story.append(Spacer(1, 0.2*inch))

        texto_formatado = laudo.laudo_texto.replace('\n', '<br/>')
        
        # Adiciona os subtítulos em negrito
        texto_formatado = texto_formatado.replace('1 DO MATERIAL', '<b>1 DO MATERIAL</b>')
        texto_formatado = texto_formatado.replace('2 DOS EXAMES', '<b>2 DOS EXAMES</b>')
        texto_formatado = texto_formatado.replace('3 DOS RESULTADOS', '<b>3 DOS RESULTADOS</b>')
        
        story.append(Paragraph(texto_formatado, style_body))

        doc.build(story)
        return response
    except LaudoGerado.DoesNotExist:
        return HttpResponse("Laudo não encontrado", status=404)
    except Exception as e:
        print(f"Erro ao gerar PDF com ReportLab: {e}")
        return HttpResponse(f"Erro ao gerar PDF: {e}", status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def listar_laudos_gerados(request):
    """
    Lista todos os laudos gerados (formato paginado compatível com Angular)
    """
    from django.core.paginator import Paginator, EmptyPage
    from .serializers import LaudoGeradoListSerializer
    
    try:
        # Parâmetros de paginação
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        
        # Query de laudos
        laudos_query = LaudoGerado.objects.select_related('template', 'gerado_por').order_by('-gerado_em')
        total_laudos = laudos_query.count()
        
        
        
        # Aplica paginação
        paginator = Paginator(laudos_query, page_size)
        
        try:
            laudos_page = paginator.page(page)
        except EmptyPage:
            laudos_page = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)
        
        # Serializa os dados
        serializer = LaudoGeradoListSerializer(laudos_page, many=True)
        
        
        # DEBUG: Ver o que está sendo retornado
        for laudo_data in serializer.data:
            print(f"   Laudo #{laudo_data['id']}: gerado_por_nome = '{laudo_data.get('gerado_por_nome')}'")
        
        # Retorna formato compatível com Angular
        return Response({
            'count': paginator.count,
            'next': laudos_page.has_next(),
            'previous': laudos_page.has_previous(),
            'results': serializer.data,
            'total_pages': paginator.num_pages,
            'current_page': page
        })
    
    except Exception as e:
        print(f"❌ ERRO ao listar laudos: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return Response(
            {
                'erro': f'Erro ao listar laudos: {str(e)}',
                'count': 0,
                'results': []
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def listar_meus_laudos(request):
    """
    Lista apenas os laudos criados pelo usuário logado
    """
    from django.core.paginator import Paginator, EmptyPage
    from .serializers import LaudoGeradoListSerializer
    
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        print(f"\n🔍 LISTAR MEUS LAUDOS - Usuário: {request.user.nome_completo}, Página: {page}")
        
        # ✅ FILTRA apenas laudos do usuário logado
        laudos_query = LaudoGerado.objects.filter(
            gerado_por=request.user
        ).select_related('template', 'gerado_por').order_by('-gerado_em')
        
        total_laudos = laudos_query.count()
        
        print(f"📊 Total de laudos do usuário: {total_laudos}")
        
        # Aplica paginação
        paginator = Paginator(laudos_query, page_size)
        
        try:
            laudos_page = paginator.page(page)
        except EmptyPage:
            laudos_page = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)
        
        # Serializa os dados
        serializer = LaudoGeradoListSerializer(laudos_page, many=True)
        
        print(f"✅ Retornando {len(serializer.data)} laudos\n")
        
        # Retorna formato compatível com Angular
        return Response({
            'count': paginator.count,
            'next': laudos_page.has_next(),
            'previous': laudos_page.has_previous(),
            'results': serializer.data,
            'total_pages': paginator.num_pages,
            'current_page': page
        })
    
    except Exception as e:
        print(f"❌ ERRO ao listar meus laudos: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return Response(
            {
                'erro': f'Erro ao listar laudos: {str(e)}',
                'count': 0,
                'results': []
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )