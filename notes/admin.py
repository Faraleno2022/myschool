from django.contrib import admin
from .models import MatiereClasse, BaremeMatiere, Evaluation, Note, BaremeAppreciation, SeuilAppreciation


@admin.register(MatiereClasse)
class MatiereClasseAdmin(admin.ModelAdmin):
    list_display = ("ecole", "classe", "nom", "coefficient", "actif")
    list_filter = ("ecole", "classe__annee_scolaire", "classe__niveau", "actif")
    search_fields = ("nom", "classe__nom", "ecole__nom")
    autocomplete_fields = ("ecole", "classe")


@admin.register(BaremeMatiere)
class BaremeMatiereAdmin(admin.ModelAdmin):
    list_display = ("ecole", "annee_scolaire", "code_serie", "nom_matiere", "coefficient", "actif")
    list_filter = ("ecole", "annee_scolaire", "code_serie", "actif")
    search_fields = ("nom_matiere", "code_serie", "ecole__nom")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("titre", "ecole", "classe", "matiere", "date", "trimestre", "coefficient")
    list_filter = ("ecole", "classe__annee_scolaire", "classe__niveau", "matiere__nom", "trimestre")
    search_fields = ("titre", "classe__nom", "matiere__nom", "ecole__nom")
    autocomplete_fields = ("ecole", "classe", "matiere")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("evaluation", "eleve", "matricule", "note", "date_saisie")
    list_filter = ("evaluation__ecole", "evaluation__classe__niveau", "evaluation__matiere__nom")
    search_fields = ("eleve__nom", "eleve__prenom", "matricule", "evaluation__titre")
    # Éviter admin.E039: l'admin Eleve doit avoir search_fields pour autocomplete.
    # On utilise raw_id_fields pour compatibilité immédiate.
    raw_id_fields = ("evaluation", "eleve")


class SeuilAppreciationInline(admin.TabularInline):
    model = SeuilAppreciation
    extra = 1
    fields = ("note_min", "appreciation", "couleur", "actif", "ordre")
    ordering = ["-note_min"]


@admin.register(BaremeAppreciation)
class BaremeAppreciationAdmin(admin.ModelAdmin):
    list_display = ("nom", "ecole", "actif", "date_creation")
    list_filter = ("ecole", "actif", "date_creation")
    search_fields = ("nom", "description", "ecole__nom")
    inlines = [SeuilAppreciationInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("ecole")


@admin.register(SeuilAppreciation)
class SeuilAppreciationAdmin(admin.ModelAdmin):
    list_display = ("bareme", "note_min", "appreciation", "couleur", "actif", "ordre")
    list_filter = ("bareme__ecole", "actif")
    search_fields = ("appreciation", "bareme__nom")
    list_editable = ("actif", "ordre")
    ordering = ("bareme", "-note_min")
