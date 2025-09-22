# spr/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView

# 1. Importa as ViewSets de todos os apps
from usuarios.views import UserRegistrationViewSet, UserManagementViewSet
from servicos_periciais.views import ServicoPericialViewSet
from cidades.views import CidadeViewSet
from cargos.views import CargoViewSet
from autoridades.views import AutoridadeViewSet
from unidades_demandantes.views import UnidadeDemandanteViewSet
from procedimentos.views import ProcedimentoViewSet
from classificacoes.views import ClassificacaoOcorrenciaViewSet
from exames.views import ExameViewSet
from procedimentos_cadastrados.views import ProcedimentoCadastradoViewSet
from tipos_documento.views import TipoDocumentoViewSet
from ocorrencias.views import OcorrenciaViewSet

# 2. Cria um roteador central para a API
router = DefaultRouter()

# 3. Registra cada ViewSet no roteador.
#    Removemos o 'basename' onde o DRF pode inferir a partir do queryset da ViewSet.
router.register(r'usuarios', UserManagementViewSet, basename='user')
router.register(r'servicos-periciais', ServicoPericialViewSet)
router.register(r'cidades', CidadeViewSet)
router.register(r'cargos', CargoViewSet)
router.register(r'autoridades', AutoridadeViewSet)
router.register(r'unidades-demandantes', UnidadeDemandanteViewSet)
router.register(r'procedimentos', ProcedimentoViewSet)
router.register(r'classificacoes', ClassificacaoOcorrenciaViewSet)
router.register(r'exames', ExameViewSet)
router.register(r'procedimentos-cadastrados', ProcedimentoCadastradoViewSet)
router.register(r'tipos-documento', TipoDocumentoViewSet)
router.register(r'ocorrencias', OcorrenciaViewSet)

# A rota 'registrar' é especial, pois não tem um queryset padrão, então o basename é necessário.
router.register(r'registrar', UserRegistrationViewSet, basename='user-registration')


# 4. Define as URLs principais do projeto
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]