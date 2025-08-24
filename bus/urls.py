from django.urls import path
from . import views

app_name = 'bus'

urlpatterns = [
    path('', views.tableau_bord, name='tableau_bord'),
    path('liste/', views.liste_abonnements, name='liste'),
    path('nouveau/', views.abonnement_create, name='nouveau'),
    path('<int:abo_id>/modifier/', views.abonnement_edit, name='modifier'),
    path('relances/', views.relances, name='relances'),
    path('relances/envoyer/', views.envoyer_relances_bus, name='envoyer_relances_bus'),
    path('relances/export/excel/', views.export_relances_excel, name='export_relances_excel'),
    path('<int:abo_id>/recu/pdf/', views.generer_recu_abonnement_pdf, name='recu_pdf'),
]
