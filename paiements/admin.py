from django.contrib import admin
from .models import TypePaiement, ModePaiement, Paiement, RemiseReduction, EcheancierPaiement


@admin.register(TypePaiement)
class TypePaiementAdmin(admin.ModelAdmin):
    list_display = ("nom", "actif")
    search_fields = ("nom",)
    list_filter = ("actif",)


@admin.register(ModePaiement)
class ModePaiementAdmin(admin.ModelAdmin):
    list_display = ("nom", "frais_supplementaires", "actif")
    search_fields = ("nom",)
    list_filter = ("actif",)


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("numero_recu", "eleve", "type_paiement", "mode_paiement", "montant", "date_paiement", "statut")
    search_fields = ("numero_recu", "eleve__nom", "eleve__prenom", "eleve__matricule")
    list_filter = ("statut", "type_paiement", "mode_paiement")
    date_hierarchy = "date_paiement"


@admin.register(RemiseReduction)
class RemiseReductionAdmin(admin.ModelAdmin):
    list_display = ("nom", "type_remise", "valeur", "motif", "actif")
    search_fields = ("nom",)
    list_filter = ("type_remise", "motif", "actif")


@admin.register(EcheancierPaiement)
class EcheancierPaiementAdmin(admin.ModelAdmin):
    list_display = ("eleve", "annee_scolaire", "statut", "total_du", "total_paye")
    search_fields = ("eleve__nom", "eleve__prenom", "eleve__matricule")
