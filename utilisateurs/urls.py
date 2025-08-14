from django.urls import path
from django.contrib.auth import views as auth_views
from .views import comptable_create_view, comptable_list_view
from .permission_views import (
    gestion_permissions, update_permissions, ajax_toggle_permission,
    bulk_update_permissions, ajax_user_permissions, export_permissions_csv
)

app_name = 'utilisateurs'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='utilisateurs/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
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
