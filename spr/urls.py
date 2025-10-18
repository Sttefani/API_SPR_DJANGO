# spr/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework_nested import routers
from rest_framework_simplejwt.views import TokenRefreshView

# Importa TODAS as suas ViewSets
from movimentacoes.views import MovimentacaoViewSet
from ordens_servico.views import OrdemServicoViewSet
from spr.views import EstatisticasCriminaisView, OcorrenciasGeoView
from usuarios.views import UserRegistrationViewSet, UserManagementViewSet, MyTokenObtainPairView, ChangePasswordView
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
from ocorrencias.views import EnderecoOcorrenciaViewSet, OcorrenciaViewSet
from ocorrencias.views_relatorios import RelatoriosGerenciaisViewSet

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
router.register(r'enderecos-ocorrencia', EnderecoOcorrenciaViewSet, basename='endereco-ocorrencia')
router.register(r'relatorios-gerenciais', RelatoriosGerenciaisViewSet, basename='relatorios-gerenciais')
router.register(r'registrar', UserRegistrationViewSet, basename='user-registration')
router.register(r'ordens-servico', OrdemServicoViewSet, basename='ordens-servico')

# =============================================================================
# ROTEADORES ANINHADOS (NÍVEL 2 - MOVIMENTAÇÕES DENTRO DE OCORRÊNCIAS)
# =============================================================================
ocorrencias_router = routers.NestedDefaultRouter(router, r'ocorrencias', lookup='ocorrencia')
ocorrencias_router.register(r'movimentacoes', MovimentacaoViewSet, basename='ocorrencia-movimentacoes')

# =============================================================================
# DEFINIÇÃO FINAL DAS URLS
# =============================================================================
urlpatterns = [
    path('admin/', admin.site.urls),

    # Inclui todas as rotas de todos os roteadores
    path('api/', include(router.urls)),
    path('api/', include(ocorrencias_router.urls)),
    
    # Análise Criminal
    path('api/analise-criminal/estatisticas/', EstatisticasCriminaisView.as_view(), name='analise-estatisticas'),
    path('api/analise-criminal/mapa/', OcorrenciasGeoView.as_view(), name='analise-mapa'),

    # Autenticação
    path('api-auth/', include('rest_framework.urls')),
    path('api/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    path('api/ia/', include('IA.urls')),  # ← ADICIONE AQUI

]