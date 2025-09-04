from django import forms
from eleves.models import Classe
from .models import MatiereClasse
from datetime import date


class ClasseNotesForm(forms.ModelForm):
    """Formulaire pour créer une classe depuis le module Notes.
    - L'école est déduite de l'utilisateur (non exposée dans le formulaire).
    - Le niveau est pré-sélectionné via l'URL (valeur initiale/readonly côté template).
    """
    class Meta:
        model = Classe
        fields = ['nom', 'niveau', 'annee_scolaire', 'capacite_max']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Nom de la classe (ex: 7ème A)"}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'annee_scolaire': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '2024-2025', 'pattern': r'^\d{4}-\d{4}$'}),
            'capacite_max': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '60'}),
        }

    def __init__(self, *args, **kwargs):
        niveau_initial = kwargs.pop('niveau_initial', None)
        super().__init__(*args, **kwargs)
        # Définir l'année scolaire par défaut si création
        if not self.instance.pk:
            current_year = date.today().year
            if date.today().month >= 9:
                self.fields['annee_scolaire'].initial = f"{current_year}-{current_year + 1}"
            else:
                self.fields['annee_scolaire'].initial = f"{current_year - 1}-{current_year}"
        # Si niveau préfixé par l'URL
        if niveau_initial:
            self.fields['niveau'].initial = niveau_initial


class MatiereClasseForm(forms.ModelForm):
    class Meta:
        model = MatiereClasse
        fields = ['nom', 'coefficient', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la matière'}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '20'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nom(self):
        nom = (self.cleaned_data.get('nom') or '').strip()
        if not nom:
            raise forms.ValidationError("Le nom de la matière est requis.")
        return nom
