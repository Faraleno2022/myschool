from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import transaction

from .models import Profil
from eleves.models import Ecole


class ComptableCreationForm(UserCreationForm):
    """Formulaire de création d'un utilisateur Comptable avec son Profil."""

    # Champs User supplémentaires
    first_name = forms.CharField(label="Prénom", max_length=150, required=False)
    last_name = forms.CharField(label="Nom", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)

    # Champs Profil
    telephone = forms.CharField(
        label="Téléphone",
        max_length=20,
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format attendu: +224XXXXXXXXX')],
    )
    ecole = forms.ModelChoiceField(
        label="École",
        queryset=Ecole.objects.all(),
        required=True,
        help_text="Sélectionnez l'école du comptable",
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
    )

    # Permissions spécifiques existantes
    peut_valider_paiements = forms.BooleanField(label="Peut valider les paiements", required=False, initial=True)
    peut_valider_depenses = forms.BooleanField(label="Peut valider les dépenses", required=False, initial=False)
    peut_generer_rapports = forms.BooleanField(label="Peut générer des rapports", required=False, initial=True)
    peut_gerer_utilisateurs = forms.BooleanField(label="Peut gérer les utilisateurs", required=False, initial=False)
    
    # Nouvelles permissions granulaires
    peut_ajouter_paiements = forms.BooleanField(
        label="Peut ajouter des paiements", 
        required=False, 
        initial=False,  # Par défaut, les comptables ne peuvent PAS ajouter de paiements
        help_text="Autoriser l'ajout de nouveaux paiements"
    )
    peut_ajouter_depenses = forms.BooleanField(
        label="Peut ajouter des dépenses", 
        required=False, 
        initial=False,  # Par défaut, les comptables ne peuvent PAS ajouter de dépenses
        help_text="Autoriser l'ajout de nouvelles dépenses"
    )
    peut_ajouter_enseignants = forms.BooleanField(
        label="Peut ajouter des enseignants", 
        required=False, 
        initial=False,  # Par défaut, les comptables ne peuvent PAS ajouter d'enseignants
        help_text="Autoriser l'ajout de nouveaux enseignants"
    )
    peut_modifier_paiements = forms.BooleanField(
        label="Peut modifier les paiements", 
        required=False, 
        initial=True,
        help_text="Autoriser la modification des paiements existants"
    )
    peut_modifier_depenses = forms.BooleanField(
        label="Peut modifier les dépenses", 
        required=False, 
        initial=True,
        help_text="Autoriser la modification des dépenses existantes"
    )
    peut_supprimer_paiements = forms.BooleanField(
        label="Peut supprimer les paiements", 
        required=False, 
        initial=False,
        help_text="Autoriser la suppression des paiements"
    )
    peut_supprimer_depenses = forms.BooleanField(
        label="Peut supprimer les dépenses", 
        required=False, 
        initial=False,
        help_text="Autoriser la suppression des dépenses"
    )
    peut_consulter_rapports = forms.BooleanField(
        label="Peut consulter les rapports", 
        required=False, 
        initial=True,
        help_text="Autoriser la consultation des rapports"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        # Ne lister ici que les champs du modèle User
        fields = (
            'username', 'first_name', 'last_name', 'email',
            'password1', 'password2',
        )

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Ordonner les écoles par nom si le champ existe
        all_ecoles = Ecole.objects.all()
        try:
            all_ecoles = all_ecoles.order_by('nom')
        except Exception:
            pass
        # Si non-superuser, restreindre à l'école de l'utilisateur
        if request and request.user.is_authenticated and not request.user.is_superuser:
            profil = getattr(request.user, 'profil', None)
            if profil and profil.ecole_id:
                self.fields['ecole'].queryset = all_ecoles.filter(pk=profil.ecole_id)
                self.fields['ecole'].initial = profil.ecole_id
            else:
                # Aucun profil/école: ne proposer aucune école pour éviter fuite
                self.fields['ecole'].queryset = all_ecoles.none()
        else:
            self.fields['ecole'].queryset = all_ecoles
        # Placeholder explicite pour la liste déroulante
        self.fields['ecole'].empty_label = "--------- Sélectionnez une école ---------"
        # Harmoniser un minimum le rendu Bootstrap
        text_like = ['username', 'first_name', 'last_name', 'email', 'telephone']
        for name in text_like:
            if name in self.fields and not isinstance(self.fields[name].widget, forms.CheckboxInput):
                css = self.fields[name].widget.attrs.get('class', '')
                self.fields[name].widget.attrs['class'] = (css + ' form-control').strip()

    @transaction.atomic
    def save(self, commit=True):
        # Crée l'utilisateur
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        user.is_active = True
        if commit:
            user.save()
        # Crée le profil lié avec toutes les permissions
        profil = Profil.objects.create(
            user=user,
            role='COMPTABLE',
            telephone=self.cleaned_data['telephone'],
            ecole=self.cleaned_data.get('ecole'),
            # Permissions existantes
            peut_valider_paiements=self.cleaned_data.get('peut_valider_paiements', False),
            peut_valider_depenses=self.cleaned_data.get('peut_valider_depenses', False),
            peut_generer_rapports=self.cleaned_data.get('peut_generer_rapports', False),
            peut_gerer_utilisateurs=self.cleaned_data.get('peut_gerer_utilisateurs', False),
            # Nouvelles permissions granulaires
            peut_ajouter_paiements=self.cleaned_data.get('peut_ajouter_paiements', False),
            peut_ajouter_depenses=self.cleaned_data.get('peut_ajouter_depenses', False),
            peut_ajouter_enseignants=self.cleaned_data.get('peut_ajouter_enseignants', False),
            peut_modifier_paiements=self.cleaned_data.get('peut_modifier_paiements', True),
            peut_modifier_depenses=self.cleaned_data.get('peut_modifier_depenses', True),
            peut_supprimer_paiements=self.cleaned_data.get('peut_supprimer_paiements', False),
            peut_supprimer_depenses=self.cleaned_data.get('peut_supprimer_depenses', False),
            peut_consulter_rapports=self.cleaned_data.get('peut_consulter_rapports', True),
        )
        return user
