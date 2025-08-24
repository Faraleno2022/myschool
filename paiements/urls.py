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
    path('relancer/<int:eleve_id>/', views.relancer_eleve, name='relancer_eleve'),
    path('relances/', views.liste_relances, name='liste_relances'),
    path('retards/envoyer/', views.envoyer_notifs_retards, name='envoyer_notifs_retards'),
    
    # Échéanciers
    path('echeancier/<int:eleve_id>/', views.echeancier_eleve, name='echeancier_eleve'),
    path('echeancier/creer/<int:eleve_id>/', views.creer_echeancier, name='creer_echeancier'),
    
    # Génération de documents
    path('recu/<int:paiement_id>/pdf/', views.generer_recu_pdf, name='generer_recu_pdf'),
    path('export/tranches-par-classe/pdf/', export_tranches_par_classe_pdf, name='export_tranches_par_classe_pdf'),
    path('export/tranches-par-classe/excel/', export_tranches_par_classe_excel, name='export_tranches_par_classe_excel'),
    path('export/liste/excel/', views.export_liste_paiements_excel, name='export_liste_paiements_excel'),
    path('rapport/remises/', views.rapport_remises, name='rapport_remises'),
    
    # Élèves soldés (année scolaire réglée)
    path('eleves-soldes/', views.liste_eleves_soldes, name='liste_eleves_soldes'),
    
    # AJAX endpoints
    path('ajax/statistiques/', views.ajax_statistiques_paiements, name='ajax_statistiques_paiements'),
    path('ajax/eleve-info/', views.ajax_eleve_info, name='ajax_eleve_info'),
    path('ajax/calculer-remise/', views.ajax_calculer_remise, name='ajax_calculer_remise'),
    path('ajax/classes/', views.ajax_classes_par_ecole, name='ajax_classes_par_ecole'),
    
    # Webhooks (Twilio)
    path('twilio/inbound/', views.twilio_inbound, name='twilio_inbound'),
    path('twilio/status-callback/', views.twilio_status_callback, name='twilio_status_callback'),
    
    # Remises
    path('remise/<int:paiement_id>/', views.appliquer_remise_paiement, name='appliquer_remise'),
    path('calculateur-remise/', views.calculateur_remise, name='calculateur_remise'),
]
