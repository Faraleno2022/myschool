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
    path('categories/activer/<int:categorie_id>/', views.activer_categorie, name='activer_categorie'),
    path('categories/desactiver/<int:categorie_id>/', views.desactiver_categorie, name='desactiver_categorie'),
    path('fournisseurs/', views.gestion_fournisseurs, name='gestion_fournisseurs'),
    path('fournisseurs/activer/<int:fournisseur_id>/', views.activer_fournisseur, name='activer_fournisseur'),
    path('fournisseurs/desactiver/<int:fournisseur_id>/', views.desactiver_fournisseur, name='desactiver_fournisseur'),
]
