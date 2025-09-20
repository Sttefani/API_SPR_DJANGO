from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServicoPericialViewSet

router = DefaultRouter()
router.register(r'servicos-periciais', ServicoPericialViewSet, basename='servico-pericial')

urlpatterns = [
    path('', include(router.urls)),
]