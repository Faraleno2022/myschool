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
    path('echeancier/assurer/<int:eleve_id>/', views.assurer_echeancier, name='assurer_echeancier'),
    path('echeancier/valider/<int:eleve_id>/', views.valider_echeancier, name='valider_echeancier'),
    
    # Génération de documents
    path('recu/<int:paiement_id>/pdf/', views.generer_recu_pdf, name='generer_recu_pdf'),
    path('export/tranches-par-classe/pdf/', export_tranches_par_classe_pdf, name='export_tranches_par_classe_pdf'),
    path('export/tranches-par-classe/excel/', export_tranches_par_classe_excel, name='export_tranches_par_classe_excel'),
    path('export/liste/excel/', views.export_liste_paiements_excel, name='export_liste_paiements_excel'),
    # Export par période (Excel)
    path('export/periode/excel/', views.export_paiements_periode_excel, name='export_paiements_periode_excel'),
    path('rapport/remises/', views.rapport_remises, name='rapport_remises'),
    
    # Rapports
    path('rapport/retards/', views.rapport_retards, name='rapport_retards'),
    path('rapport/encaissements/', views.rapport_encaissements, name='rapport_encaissements'),
    
    # Élèves soldés (année scolaire réglée)
    path('eleves-soldes/', views.liste_eleves_soldes, name='liste_eleves_soldes'),
    
    # API JSON Paiements
    path('api/paiements/', views.api_paiements_list, name='api_paiements_list'),
    path('api/paiements/<int:pk>/', views.api_paiement_detail, name='api_paiement_detail'),
    
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
    # Annulation de remise(s)
    path('remise/<int:paiement_id>/annuler/', views.annuler_remise_paiement, name='annuler_remise_paiement'),
    path('remise/<int:paiement_id>/annuler/<int:remise_id>/', views.annuler_remise_paiement, name='annuler_remise_paiement_unique'),
    path('calculateur-remise/', views.calculateur_remise, name='calculateur_remise'),
]


