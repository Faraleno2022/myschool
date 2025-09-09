from django.urls import path
from . import views
from .views_creation_etablissement import creer_etablissement, verifier_statut_etablissement

app_name = 'inscription_ecoles'

urlpatterns = [
    # Inscription publique
    path('inscription/', views.InscriptionEcoleView.as_view(), name='inscription_ecole'),
    path('inscription-complete/', views.inscription_ecole_complete, name='inscription_ecole_complete'),
    path('merci/', views.inscription_merci, name='inscription_merci'),
    
    # Création de compte
    path('creer-etablissement/', creer_etablissement, name='creer_etablissement'),
    path('verifier-statut/', verifier_statut_etablissement, name='verifier_statut_etablissement'),
    
    # Tableau de bord école
    path('tableau-bord/', views.tableau_bord_ecole, name='tableau_bord_ecole'),
    path('configuration/', views.configuration_ecole, name='configuration_ecole'),
    path('documents/', views.personnaliser_documents, name='personnaliser_documents'),
    
    # API
    path('apercu-document/', views.apercu_document, name='apercu_document'),
    
    # Administration
    path('admin/demandes/', views.admin_demandes_inscription, name='admin_demandes_inscription'),
    path('admin/traiter/<int:demande_id>/', views.traiter_demande_inscription, name='traiter_demande_inscription'),
]
