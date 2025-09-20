# spr/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# 1. Importa as ViewSets de todos os apps que têm rotas na API
from usuarios.views import UserRegistrationViewSet, UserManagementViewSet
from servicos_periciais.views import ServicoPericialViewSet
from cidades.views import CidadeViewSet
from cargos.views import CargoViewSet
from autoridades.views import AutoridadeViewSet # <-- IMPORTE A NOVA VIEW
from unidades_demandantes.views import UnidadeDemandanteViewSet # <-- IMPORTE A NOVA VIEW
from procedimentos.views import ProcedimentoViewSet # <-- IMPORTE A NOVA VIEW
from classificacoes.views import ClassificacaoOcorrenciaViewSet # <-- IMPORTE
from exames.views import ExameViewSet # <-- IMPORTE
from procedimentos_cadastrados.views import ProcedimentoCadastradoViewSet # <-- IMPORTE
from tipos_documento.views import TipoDocumentoViewSet # <-- IMPORTE A NOVA VIEW
from ocorrencias.views import OcorrenciaViewSet




# 2. Cria um roteador central para a API
router = DefaultRouter()

# 3. Registra cada ViewSet no roteador, definindo sua URL e nome base
router.register(r'registrar', UserRegistrationViewSet, basename='user-registration')
router.register(r'usuarios', UserManagementViewSet, basename='user-management')
router.register(r'servicos-periciais', ServicoPericialViewSet, basename='servico-pericial')
router.register(r'cidades', CidadeViewSet, basename='cidade')
router.register(r'cargos', CargoViewSet, basename='cargo')
router.register(r'autoridades', AutoridadeViewSet, basename='autoridade') # <-- REGISTRE A NOVA ROTA
router.register(r'unidades-demandantes', UnidadeDemandanteViewSet, basename='unidade-demandante')
router.register(r'procedimentos', ProcedimentoViewSet, basename='procedimento') # <-- REGISTRE A NOVA ROTA
router.register(r'classificacoes', ClassificacaoOcorrenciaViewSet, basename='classificacaoocorrencia') # <-- REGISTRE
router.register(r'exames', ExameViewSet, basename='exame') # <-- REGISTRE
router.register(r'procedimentos-cadastrados', ProcedimentoCadastradoViewSet, basename='procedimentocadastrado') # <-- REGISTRE
router.register(r'tipos-documento', TipoDocumentoViewSet, basename='tipodocumento') # <-- REGISTRE A NOVA ROTA
router.register(r'ocorrencias', OcorrenciaViewSet, basename='ocorrencia') # <-- REGISTRE A NOVA ROTA




# <-- REGISTRE A NOVA ROTA



# 4. Define as URLs principais do projeto
urlpatterns = [
    # Rota para a interface de administração padrão do Django
    path('admin/', admin.site.urls),

    # Rota principal da nossa API, controlada pelo roteador que criamos
    path('api/', include(router.urls)),

    # Rotas para autenticação
    path('api-auth/', include('rest_framework.urls')), # Para login/logout na API de teste
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # Para obter token JWT
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # Para atualizar token JWT
]