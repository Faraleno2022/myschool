from django import forms
from django.core.exceptions import ValidationError
from .models import Enseignant, TypeEnseignant, StatutEnseignant
from eleves.models import Ecole


class EnseignantForm(forms.ModelForm):
    """Formulaire pour créer/modifier un enseignant"""
    
    class Meta:
        model = Enseignant
        fields = [
            'nom', 'prenoms', 'telephone', 'email', 'adresse',
            'ecole', 'type_enseignant', 'statut', 
            'taux_horaire', 'salaire_fixe', 'heures_mensuelles', 'date_embauche'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de famille'
            }),
            'prenoms': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénoms'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+224 XXX XX XX XX'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adresse complète'
            }),
            'ecole': forms.Select(attrs={
                'class': 'form-select'
            }),
            'type_enseignant': forms.Select(attrs={
                'class': 'form-select'
            }),
            'statut': forms.Select(attrs={
                'class': 'form-select'
            }),
            'taux_horaire': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Taux horaire en GNF',
                'step': '0.01'
            }),
            'salaire_fixe': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Salaire fixe en GNF',
                'step': '0.01'
            }),
            'heures_mensuelles': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre d\'heures par mois',
                'step': '0.25',
                'min': '0'
            }),
            'date_embauche': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
        labels = {
            'nom': 'Nom de famille *',
            'prenoms': 'Prénoms *',
            'telephone': 'Téléphone',
            'email': 'Email',
            'adresse': 'Adresse',
            'ecole': 'École *',
            'type_enseignant': 'Type d\'enseignant *',
            'statut': 'Statut',
            'taux_horaire': 'Taux horaire (GNF)',
            'salaire_fixe': 'Salaire fixe (GNF)',
            'heures_mensuelles': 'Heures mensuelles',
            'date_embauche': 'Date d\'embauche *',
        }
        help_texts = {
            'taux_horaire': 'Pour les enseignants du secondaire uniquement',
            'salaire_fixe': 'Pour garderie, maternelle, primaire et administrateurs',
            'heures_mensuelles': 'Nombre d\'heures de travail prévues par mois (pour calcul précis du salaire)',
            'date_embauche': 'Date d\'entrée en fonction',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Rendre certains champs obligatoires
        self.fields['nom'].required = True
        self.fields['prenoms'].required = True
        self.fields['ecole'].required = True
        self.fields['type_enseignant'].required = True
        self.fields['date_embauche'].required = True
        
        # Définir le statut par défaut
        if not self.instance.pk:
            self.fields['statut'].initial = StatutEnseignant.ACTIF

    def clean(self):
        cleaned_data = super().clean()
        type_enseignant = cleaned_data.get('type_enseignant')
        taux_horaire = cleaned_data.get('taux_horaire')
        salaire_fixe = cleaned_data.get('salaire_fixe')
        heures_mensuelles = cleaned_data.get('heures_mensuelles')

        # Validation selon le type d'enseignant
        if type_enseignant == TypeEnseignant.SECONDAIRE:
            if not taux_horaire:
                raise ValidationError({
                    'taux_horaire': 'Le taux horaire est obligatoire pour les enseignants du secondaire.'
                })
            if not heures_mensuelles:
                raise ValidationError({
                    'heures_mensuelles': 'Le nombre d\'heures mensuelles est obligatoire pour les enseignants du secondaire.'
                })
            if salaire_fixe:
                cleaned_data['salaire_fixe'] = None  # Effacer le salaire fixe
        else:
            if not salaire_fixe:
                raise ValidationError({
                    'salaire_fixe': f'Le salaire fixe est obligatoire pour les enseignants de type {type_enseignant}.'
                })
            if taux_horaire:
                cleaned_data['taux_horaire'] = None  # Effacer le taux horaire
        
        # Validation des heures mensuelles
        if heures_mensuelles and heures_mensuelles <= 0:
            raise ValidationError({
                'heures_mensuelles': 'Le nombre d\'heures mensuelles doit être supérieur à 0.'
            })
        
        if heures_mensuelles and heures_mensuelles > 200:
            raise ValidationError({
                'heures_mensuelles': 'Le nombre d\'heures mensuelles ne peut pas dépasser 200 heures par mois.'
            })

        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Vérifier l'unicité de l'email (sauf pour l'instance actuelle)
            existing = Enseignant.objects.filter(email=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('Un enseignant avec cet email existe déjà.')
        return email

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if telephone:
            # Validation basique du format téléphone guinéen
            telephone = telephone.replace(' ', '').replace('-', '')
            if not telephone.startswith('+224') and not telephone.startswith('224'):
                if len(telephone) == 9 and telephone.startswith(('6', '7')):
                    telephone = '+224' + telephone
                else:
                    raise ValidationError('Format de téléphone invalide. Utilisez le format guinéen.')
        return telephone
