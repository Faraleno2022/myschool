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
]
