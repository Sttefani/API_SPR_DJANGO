from django.urls import path
from . import views

urlpatterns = [
    path('chat/iniciar/', views.iniciar_sessao, name='iniciar_sessao'),
    path('chat/mensagem/', views.enviar_mensagem, name='enviar_mensagem'),
    path('chat/historico/<str:session_key>/', views.obter_historico, name='obter_historico'),
    path('chat/gerar-laudo/', views.gerar_laudo, name='gerar_laudo'),
]