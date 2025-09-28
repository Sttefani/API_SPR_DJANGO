# spr/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework_nested import routers
# REMOVIDO TokenObtainPairView DAQUI PARA EVITAR CONFLITO
from rest_framework_simplejwt.views import TokenRefreshView

# Importa TODAS as suas ViewSets
from movimentacoes.views import MovimentacaoViewSet
from ordens_servico.views import OrdemServicoViewSet
# ADICIONADO MyTokenObtainPairView PARA O LOGIN CUSTOMIZADO
from usuarios.views import UserRegistrationViewSet, UserManagementViewSet, MyTokenObtainPairView
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
from fichas.views import (
    FichaLocalCrimeViewSet, VitimaViewSet, VestigioViewSet, LacreViewSet,
    FichaAcidenteTransitoViewSet, VeiculoViewSet,
    FichaConstatacaoSubstanciaViewSet, ItemSubstanciaViewSet,
    FichaDocumentoscopiaViewSet, ItemDocumentoscopiaViewSet,
    FichaMaterialDiversoViewSet, ItemMaterialViewSet
)

# =============================================================================
# ROTEADOR NÍVEL 1 (PRINCIPAL)
# =============================================================================
router = routers.DefaultRouter()
# Registra todos os apps que são "pais" ou independentes
router.register(r'usuarios', UserManagementViewSet)
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
router.register(r'registrar', UserRegistrationViewSet, basename='user-registration')


# =============================================================================
# ROTEADORES ANINHADOS (NÍVEL 2 - FICHAS DENTRO DE OCORRÊNCIAS)
# =============================================================================
ocorrencias_router = routers.NestedDefaultRouter(router, r'ocorrencias', lookup='ocorrencia')
ocorrencias_router.register(r'fichas-local-crime', FichaLocalCrimeViewSet, basename='ocorrencia-fichas-local-crime')
ocorrencias_router.register(r'fichas-acidente-transito', FichaAcidenteTransitoViewSet, basename='ocorrencia-fichas-acidente-transito')
ocorrencias_router.register(r'fichas-constatacao-substancia', FichaConstatacaoSubstanciaViewSet, basename='ocorrencia-fichas-constatacao-substancia')
ocorrencias_router.register(r'fichas-documentoscopia', FichaDocumentoscopiaViewSet, basename='ocorrencia-fichas-documentoscopia')
ocorrencias_router.register(r'fichas-material-diverso', FichaMaterialDiversoViewSet, basename='ocorrencia-fichas-material-diverso')
ocorrencias_router.register(r'movimentacoes', MovimentacaoViewSet, basename='ocorrencia-movimentacoes')
ocorrencias_router.register(r'ordens-servico', OrdemServicoViewSet, basename='ocorrencia-ordensservico')


# =============================================================================
# ROTEADORES ANINHADOS (NÍVEL 3 - ITENS DENTRO DE FICHAS)
# =============================================================================
# --- Itens dentro de FichaLocalCrime ---
fichalocalcrime_router = routers.NestedDefaultRouter(ocorrencias_router, r'fichas-local-crime', lookup='fichalocalcrime')
fichalocalcrime_router.register(r'vitimas', VitimaViewSet, basename='fichalocalcrime-vitimas')
fichalocalcrime_router.register(r'vestigios', VestigioViewSet, basename='fichalocalcrime-vestigios')

# --- Itens dentro de FichaAcidenteTransito ---
fichaacidentetransito_router = routers.NestedDefaultRouter(ocorrencias_router, r'fichas-acidente-transito', lookup='fichaacidentetransito')
fichaacidentetransito_router.register(r'veiculos', VeiculoViewSet, basename='fichaacidentetransito-veiculos')

# --- Itens dentro de FichaConstatacaoSubstancia ---
fichaconst_router = routers.NestedDefaultRouter(ocorrencias_router, r'fichas-constatacao-substancia', lookup='fichaconstatacaosubstancia')
fichaconst_router.register(r'itens-substancia', ItemSubstanciaViewSet, basename='fichaconst-itens')
fichaconst_router.register(r'lacres', LacreViewSet, basename='fichaconst-lacres')

# --- Itens dentro de FichaDocumentoscopia ---
fichadoc_router = routers.NestedDefaultRouter(ocorrencias_router, r'fichas-documentoscopia', lookup='fichadocumentoscopia')
fichadoc_router.register(r'itens-documentoscopia', ItemDocumentoscopiaViewSet, basename='fichadoc-itens')

# --- Itens dentro de FichaMaterialDiverso ---
fichamatdiv_router = routers.NestedDefaultRouter(ocorrencias_router, r'fichas-material-diverso', lookup='fichamaterialdiverso')
fichamatdiv_router.register(r'itens-material', ItemMaterialViewSet, basename='fichamatdiv-itens')

# =============================================================================
# ROTEADORES ANINHADOS (NÍVEL 4 - LACRES DENTRO DE VESTÍGIOS)
# =============================================================================
vestigios_router = routers.NestedDefaultRouter(fichalocalcrime_router, r'vestigios', lookup='vestigio')
vestigios_router.register(r'lacres', LacreViewSet, basename='vestigio-lacres')


# =============================================================================
# DEFINIÇÃO FINAL DAS URLS
# =============================================================================
urlpatterns = [
    path('admin/', admin.site.urls),

    # Inclui todas as rotas de todos os roteadores
    path('api/', include(router.urls)),
    path('api/', include(ocorrencias_router.urls)),
    path('api/', include(fichalocalcrime_router.urls)),
    path('api/', include(fichaacidentetransito_router.urls)),
    path('api/', include(fichaconst_router.urls)),
    path('api/', include(fichadoc_router.urls)),
    path('api/', include(fichamatdiv_router.urls)),
    path('api/', include(vestigios_router.urls)),

    # Autenticação
    path('api-auth/', include('rest_framework.urls')),
    # URL DE LOGIN MODIFICADA PARA USAR A VIEW CUSTOMIZADA
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]