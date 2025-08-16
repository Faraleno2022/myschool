from django.urls import path
from . import views

app_name = 'administration'

urlpatterns = [
    # Gestion des bases de données
    path('', views.database_management, name='database_management'),
    path('model/<str:app_label>/<str:model_name>/', views.model_list_view, name='model_list'),
    path('model/<str:app_label>/<str:model_name>/<int:object_id>/', views.model_detail_view, name='model_detail'),
    path('model/<str:app_label>/<str:model_name>/<int:object_id>/delete/', views.model_delete_view, name='model_delete'),
    path('model/<str:app_label>/<str:model_name>/bulk-delete/', views.model_bulk_delete_view, name='model_bulk_delete'),
    
    # Réinitialisation système
    path('reset/', views.system_reset_dashboard, name='system_reset_dashboard'),
    path('reset/confirm/', views.confirm_system_reset, name='confirm_system_reset'),
    path('backup/', views.backup_before_reset, name='backup_before_reset'),
    
    # Gestion des retards de paiement
    path('retards-paiement/', views.eleves_retard_paiement, name='eleves_retard_paiement'),
    path('envoyer-rappel/', views.envoyer_rappel_paiement, name='envoyer_rappel_paiement'),
]
