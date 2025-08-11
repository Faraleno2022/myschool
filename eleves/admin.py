from django.contrib import admin
from .models import Ecole, Classe


@admin.register(Ecole)
class EcoleAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "email", "directeur")
    search_fields = ("nom", "directeur", "telephone", "email")


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("nom", "niveau", "annee_scolaire", "ecole")
    list_filter = ("ecole", "niveau", "annee_scolaire")
    search_fields = ("nom", "ecole__nom")
