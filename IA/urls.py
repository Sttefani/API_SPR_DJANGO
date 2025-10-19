from django.urls import path
from . import views

# Este ficheiro define as rotas específicas para o app 'IA'
# O prefixo '/api/ia/' já foi definido no urls.py principal do projeto.

urlpatterns = [
    # ===== Rotas para o Chat com IA =====
    path('chat/iniciar/', views.iniciar_sessao, name='iniciar_sessao'),
    path('chat/mensagem/', views.enviar_mensagem, name='enviar_mensagem'),
    path('chat/historico/<str:session_key>/', views.obter_historico, name='obter_historico'),
    path('chat/gerar-laudo/', views.gerar_laudo, name='gerar_laudo'),

    # ===== Rotas para Laudos via Template (THC) =====
    path('laudo/thc/gerar/', views.gerar_laudo_thc_view, name='gerar_laudo_thc'),
    path('laudo/thc/campos/', views.obter_campos_laudo_thc, name='campos_laudo_thc'),
    path('laudo/<int:laudo_id>/', views.obter_laudo_gerado, name='obter_laudo'),
    path('laudos/listar/meus/', views.listar_meus_laudos, name='listar_meus_laudos'),
    path('laudos/listar/', views.listar_laudos_gerados, name='listar_laudos'),

    # Rota para gerar PDF
    path('laudo/<int:laudo_id>/pdf/', views.gerar_laudo_pdf_view, name='gerar_laudo_pdf'),
]

