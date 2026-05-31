# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_nested import routers
from rest_framework_simplejwt.views import TokenRefreshView

# Importa TODAS as suas ViewSets
from movimentacoes.views import MovimentacaoViewSet
from ordens_servico.views import OrdemServicoViewSet
from spr.views import (
    DashboardCriminalView,
    EstatisticasCriminaisView,
    OcorrenciasGeoView,
)
from usuarios.views import (
    UserRegistrationViewSet,
    UserManagementViewSet,
    MyTokenObtainPairView,
    ChangePasswordView,
)
from servicos_periciais.views import ServicoPericialViewSet
from cidades.views import CidadeViewSet, BairroViewSet  # ← ADICIONADO BairroViewSet
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
from custodia.views import (
    VestigioViewSet,
    VestigioMovimentacaoViewSet,
    DNAViewSet,
    CustodiaResumoView,
    DashboardExternoView,
    DashboardCustodianteView,
)

# =============================================================================
# ROTEADOR NÍVEL 1 (PRINCIPAL)
# =============================================================================
router = routers.DefaultRouter()
router.register(r"usuarios", UserManagementViewSet)
router.register(r"servicos-periciais", ServicoPericialViewSet)
router.register(r"cidades", CidadeViewSet)
router.register(r"bairros", BairroViewSet)  # ← ADICIONADO
router.register(r"cargos", CargoViewSet)
router.register(r"autoridades", AutoridadeViewSet)
router.register(r"unidades-demandantes", UnidadeDemandanteViewSet)
router.register(r"procedimentos", ProcedimentoViewSet)
router.register(r"classificacoes", ClassificacaoOcorrenciaViewSet)
router.register(r"exames", ExameViewSet)
router.register(r"procedimentos-cadastrados", ProcedimentoCadastradoViewSet)
router.register(r"tipos-documento", TipoDocumentoViewSet)
router.register(r"ocorrencias", OcorrenciaViewSet)
router.register(
    r"enderecos-ocorrencia", EnderecoOcorrenciaViewSet, basename="endereco-ocorrencia"
)
router.register(
    r"relatorios-gerenciais",
    RelatoriosGerenciaisViewSet,
    basename="relatorios-gerenciais",
)
router.register(r"registrar", UserRegistrationViewSet, basename="user-registration")
router.register(r"ordens-servico", OrdemServicoViewSet, basename="ordens-servico")
router.register(r"custodia/vestigios", VestigioViewSet, basename="vestigio")
router.register(r"custodia/movimentacoes", VestigioMovimentacaoViewSet, basename="vestigio-movimentacao")
router.register(r"custodia/dnas", DNAViewSet, basename="dna")

# =============================================================================
# ROTEADORES ANINHADOS
# =============================================================================
ocorrencias_router = routers.NestedDefaultRouter(
    router, r"ocorrencias", lookup="ocorrencia"
)
ocorrencias_router.register(
    r"movimentacoes", MovimentacaoViewSet, basename="ocorrencia-movimentacoes"
)

# =============================================================================
# DEFINIÇÃO FINAL DAS URLS
# =============================================================================
urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/ocorrencias/dados-calendario/",
        OcorrenciaViewSet.as_view({"get": "dados_calendario"}),
        name="ocorrencias-calendario",
    ),
    # Inclui todas as rotas de todos os roteadores
    path("api/", include(router.urls)),
    path("api/", include(ocorrencias_router.urls)),
    # Análise Criminal
    path(
        "api/analise-criminal/estatisticas/",
        EstatisticasCriminaisView.as_view(),
        name="analise-estatisticas",
    ),
    path(
        "api/analise-criminal/mapa/", OcorrenciasGeoView.as_view(), name="analise-mapa"
    ),
    path(
        "api/analise-criminal/dashboard/",
        DashboardCriminalView.as_view(),
        name="analise-dashboard",
    ),  # 🆕 NOVA LINHA
    # Widget de resumo de custódia (perito, operacional, admin, super_admin)
    path(
        "api/custodia/resumo/",
        CustodiaResumoView.as_view(),
        name="custodia-resumo",
    ),
    # Dashboards por perfil — Custódia
    path(
        "api/custodia/dashboard/externo/",
        DashboardExternoView.as_view(),
        name="custodia-dashboard-externo",
    ),
    path(
        "api/custodia/dashboard/custodiante/",
        DashboardCustodianteView.as_view(),
        name="custodia-dashboard-custodiante",
    ),
    # Autenticação
    path("api-auth/", include("rest_framework.urls")),
    path("api/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("api/token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Auditoria
    path("api/auditlog/", include("auditlog.urls")),
]

# Servir arquivos de mídia (fotos de DNA, etc.).
# Em produção (DEBUG=False) o ideal é o nginx/whitenoise servir /media/,
# mas mantemos o fallback do Django para o ambiente atual funcionar.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
