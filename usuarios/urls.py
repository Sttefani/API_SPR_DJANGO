# usuarios/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
# Adicione UserManagementViewSet à linha de import abaixo
from .views import ChangePasswordView, UserRegistrationViewSet, UserManagementViewSet

router = DefaultRouter()
router.register(r'registrar', UserRegistrationViewSet, basename='user-registration')
# Adicione esta linha para registrar o novo endpoint
router.register(r'usuarios', UserManagementViewSet, basename='user-management')

urlpatterns = [
    path('', include(router.urls)),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

]