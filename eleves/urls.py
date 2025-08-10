from django.urls import path
from . import views

app_name = 'eleves'

urlpatterns = [
    # Liste et recherche des élèves
    path('', views.liste_eleves, name='liste_eleves'),
    path('liste/', views.liste_eleves, name='liste_eleves'),
    
    # Détails d'un élève
    path('<int:eleve_id>/', views.detail_eleve, name='detail_eleve'),
    
    # Gestion des élèves
    path('ajouter/', views.ajouter_eleve, name='ajouter_eleve'),
    path('<int:eleve_id>/modifier/', views.modifier_eleve, name='modifier_eleve'),
    path('<int:eleve_id>/supprimer/', views.supprimer_eleve, name='supprimer_eleve'),
    
    # Gestion des classes
    path('classes/', views.gestion_classes, name='gestion_classes'),
    
    # Statistiques
    path('statistiques/', views.statistiques_eleves, name='statistiques_eleves'),
    
    # AJAX
    path('ajax/classes-par-ecole/<int:ecole_id>/', views.ajax_classes_par_ecole, name='ajax_classes_par_ecole'),
    path('ajax/statistiques/', views.ajax_statistiques_eleves, name='ajax_statistiques_eleves'),
]
