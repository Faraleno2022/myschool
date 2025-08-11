from django.contrib import admin
from .models import Ecole, Classe, GrilleTarifaire


@admin.register(Ecole)
class EcoleAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "email", "directeur")
    search_fields = ("nom", "directeur", "telephone", "email")


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("nom", "niveau", "annee_scolaire", "ecole")
    list_filter = ("ecole", "niveau", "annee_scolaire")
    search_fields = ("nom", "ecole__nom")


@admin.register(GrilleTarifaire)
class GrilleTarifaireAdmin(admin.ModelAdmin):
    list_display = ("ecole", "niveau", "annee_scolaire", "frais_inscription", "tranche_1", "tranche_2", "tranche_3")
    list_filter = ("ecole", "niveau", "annee_scolaire")
    search_fields = ("ecole__nom",)
