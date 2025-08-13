from django.urls import path
from . import views

app_name = 'administration'

urlpatterns = [
    # Réinitialisation système
    path('reset/', views.system_reset_dashboard, name='system_reset_dashboard'),
    path('reset/confirm/', views.confirm_system_reset, name='confirm_system_reset'),
    path('backup/', views.backup_before_reset, name='backup_before_reset'),
]
