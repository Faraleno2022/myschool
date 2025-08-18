from django.contrib import admin
from .models import AbonnementBus

@admin.register(AbonnementBus)
class AbonnementBusAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'montant', 'periodicite', 'date_debut', 'date_expiration', 'statut', 'zone', 'point_arret')
    list_filter = ('statut', 'periodicite', 'zone')
    search_fields = ('eleve__nom', 'eleve__prenom', 'eleve__matricule', 'zone', 'point_arret', 'contact_parent')
