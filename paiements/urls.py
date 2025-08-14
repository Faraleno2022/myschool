from django.urls import path
from . import views
from .views_tranches import export_tranches_par_classe_pdf, export_tranches_par_classe_excel

app_name = 'paiements'

urlpatterns = [
    # Tableau de bord
    path('', views.tableau_bord_paiements, name='tableau_bord'),
    
    # Gestion des paiements
    path('liste/', views.liste_paiements, name='liste_paiements'),
    path('detail/<int:paiement_id>/', views.detail_paiement, name='detail_paiement'),
    path('ajouter/', views.ajouter_paiement, name='ajouter_paiement'),
    path('ajouter/<int:eleve_id>/', views.ajouter_paiement, name='ajouter_paiement_eleve'),
    path('valider/<int:paiement_id>/', views.valider_paiement, name='valider_paiement'),
    
    # Échéanciers
    path('echeancier/<int:eleve_id>/', views.echeancier_eleve, name='echeancier_eleve'),
    path('echeancier/creer/<int:eleve_id>/', views.creer_echeancier, name='creer_echeancier'),
    
    # Génération de documents
    path('recu/<int:paiement_id>/pdf/', views.generer_recu_pdf, name='generer_recu_pdf'),
    path('export/tranches-par-classe/pdf/', export_tranches_par_classe_pdf, name='export_tranches_par_classe_pdf'),
    path('export/tranches-par-classe/excel/', export_tranches_par_classe_excel, name='export_tranches_par_classe_excel'),
    
    # AJAX endpoints
    path('ajax/statistiques/', views.ajax_statistiques_paiements, name='ajax_statistiques_paiements'),
    path('ajax/eleve-info/', views.ajax_eleve_info, name='ajax_eleve_info'),
    path('ajax/calculer-remise/', views.ajax_calculer_remise, name='ajax_calculer_remise'),
    
    # Remises
    path('remise/<int:paiement_id>/', views.appliquer_remise_paiement, name='appliquer_remise'),
    path('calculateur-remise/', views.calculateur_remise, name='calculateur_remise'),
]
