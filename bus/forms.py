from django import forms
from .models import AbonnementBus

class AbonnementBusForm(forms.ModelForm):
    class Meta:
        model = AbonnementBus
        fields = [
            'eleve', 'montant', 'periodicite', 'date_debut', 'date_expiration', 'statut',
            'alerte_avant_jours', 'zone', 'itineraire', 'point_arret', 'contact_parent', 'observations'
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_expiration': forms.DateInput(attrs={'type': 'date'}),
        }
