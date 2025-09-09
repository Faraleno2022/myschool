from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    comptable_create_view, comptable_list_view, changer_ecole_view,
    gestion_utilisateurs_view, profil_view
)
from .security_views import secure_login, secure_logout, SecurePasswordChangeView, verify_phone
from .permission_views import (
    gestion_permissions, update_permissions, ajax_toggle_permission,
    bulk_update_permissions, ajax_user_permissions, export_permissions_csv
)

app_name = 'utilisateurs'

urlpatterns = [
    # Auth sécurisé (utiliser les vues custom pour limiter les écritures DB)
    path('login/', secure_login, name='login'),
    path('logout/', secure_logout, name='logout'),
    path('password/change/', SecurePasswordChangeView.as_view(), name='password_change'),
    path('verify-phone/', verify_phone, name='verify_phone'),
    
    # Gestion multi-tenant
    path('changer-ecole/', changer_ecole_view, name='changer_ecole'),
    path('profil/', profil_view, name='profil'),
    path('gestion/', gestion_utilisateurs_view, name='gestion_utilisateurs'),
    
    # Gestion des comptables
    path('comptables/ajouter/', comptable_create_view, name='comptable_create'),
    path('comptables/', comptable_list_view, name='comptable_list'),
    
    # Gestion des permissions
    path('permissions/', gestion_permissions, name='gestion_permissions'),
    path('permissions/update/<int:comptable_id>/', update_permissions, name='update_permissions'),
    path('permissions/bulk-update/', bulk_update_permissions, name='bulk_update_permissions'),
    path('permissions/export/', export_permissions_csv, name='export_permissions_csv'),
    
    # AJAX endpoints
    path('ajax/toggle-permission/', ajax_toggle_permission, name='ajax_toggle_permission'),
    path('ajax/user-permissions/', ajax_user_permissions, name='ajax_user_permissions'),
]
