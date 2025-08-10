from django.urls import path
from . import views

app_name = 'depenses'

urlpatterns = [
    # Tableau de bord principal
    path('', views.tableau_bord, name='tableau_bord'),
    
    # Gestion des dépenses
    path('liste/', views.liste_depenses, name='liste_depenses'),
    path('ajouter/', views.ajouter_depense, name='ajouter_depense'),
    path('<int:depense_id>/', views.detail_depense, name='detail_depense'),
    path('<int:depense_id>/modifier/', views.modifier_depense, name='modifier_depense'),
    path('<int:depense_id>/valider/', views.valider_depense, name='valider_depense'),
    path('<int:depense_id>/marquer-payee/', views.marquer_payee, name='marquer_payee'),
    
    # Gestion des catégories et fournisseurs
    path('categories/', views.gestion_categories, name='gestion_categories'),
    path('fournisseurs/', views.gestion_fournisseurs, name='gestion_fournisseurs'),
]
