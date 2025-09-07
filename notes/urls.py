from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('', views.tableau_bord, name='tableau_bord'),
    # Classes
    path('classes/<str:niveau>/nouvelle/', views.creer_classe, name='creer_classe'),
    path('classes/<int:classe_id>/supprimer/', views.supprimer_classe, name='supprimer_classe'),
    path('classes/<int:classe_id>/matieres/', views.matieres_classe, name='matieres_classe'),
    # Matières
    path('classes/<int:classe_id>/matieres/nouvelle/', views.creer_matiere, name='creer_matiere'),
    path('matieres/<int:pk>/supprimer/', views.supprimer_matiere, name='supprimer_matiere'),
    # Évaluations & Saisie notes
    path('classes/<int:classe_id>/matieres/<int:matiere_id>/evaluations/nouvelle/', views.creer_evaluation, name='creer_evaluation'),
    path('classes/<int:classe_id>/matieres/<int:matiere_id>/evaluations/', views.evaluations_matiere, name='evaluations_matiere'),
    path('evaluations/<int:evaluation_id>/saisie/', views.saisie_notes, name='saisie_notes'),
    path('evaluations/<int:evaluation_id>/', views.evaluation_detail, name='evaluation_detail'),
    # Bulletin PDF
    path('classes/<int:classe_id>/eleves/<int:eleve_id>/bulletin/<str:trimestre>/', views.bulletin_pdf, name='bulletin_pdf'),
    path('classes/<int:classe_id>/bulletins/<str:trimestre>/', views.bulletins_classe_pdf, name='bulletins_classe_pdf'),
    # Export Excel des notes d'une matière
    path('classes/<int:classe_id>/matieres/<int:matiere_id>/export/<str:trimestre>/', views.export_notes_excel, name='export_notes_excel'),
    # Bulletins annuels
    path('classes/<int:classe_id>/eleves/<int:eleve_id>/bulletin-annuel/', views.bulletin_annuel_pdf, name='bulletin_annuel_pdf'),
    path('classes/<int:classe_id>/bulletins-annuels/', views.bulletins_annuels_classe_pdf, name='bulletins_annuels_classe_pdf'),
    # Classements
    path('classes/<int:classe_id>/classement/', views.classement_classe, name='classement_classe'),
    path('classes/<int:classe_id>/classement/<str:trimestre>/', views.classement_classe, name='classement_classe'),
    path('classes/<int:classe_id>/classement/<str:trimestre>/pdf/', views.classement_classe_pdf, name='classement_classe_pdf'),
    path('classes/<int:classe_id>/classement/<str:trimestre>/excel/', views.classement_classe_excel, name='classement_classe_excel'),
    # Cartes scolaires
    path('classes/<int:classe_id>/cartes-scolaires/', views.cartes_scolaires_classe, name='cartes_scolaires_classe'),
    path('classes/<int:classe_id>/cartes-scolaires/pdf/', views.cartes_scolaires_pdf, name='cartes_scolaires_pdf'),
    # Carte individuelle par matricule
    path('carte-eleve/<str:matricule>/', views.carte_eleve_pdf, name='carte_eleve_pdf'),
]
