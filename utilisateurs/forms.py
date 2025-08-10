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
        required=False,
        help_text="Associez le comptable à une école (facultatif)",
    )

    # Permissions spécifiques
    peut_valider_paiements = forms.BooleanField(label="Peut valider les paiements", required=False, initial=True)
    peut_valider_depenses = forms.BooleanField(label="Peut valider les dépenses", required=False, initial=False)
    peut_generer_rapports = forms.BooleanField(label="Peut générer des rapports", required=False, initial=True)
    peut_gerer_utilisateurs = forms.BooleanField(label="Peut gérer les utilisateurs", required=False, initial=False)

    class Meta(UserCreationForm.Meta):
        model = User
        # Ne lister ici que les champs du modèle User
        fields = (
            'username', 'first_name', 'last_name', 'email',
            'password1', 'password2',
        )

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
        # Crée le profil lié
        profil = Profil.objects.create(
            user=user,
            role='COMPTABLE',
            telephone=self.cleaned_data['telephone'],
            ecole=self.cleaned_data.get('ecole'),
            peut_valider_paiements=self.cleaned_data.get('peut_valider_paiements', False),
            peut_valider_depenses=self.cleaned_data.get('peut_valider_depenses', False),
            peut_generer_rapports=self.cleaned_data.get('peut_generer_rapports', False),
            peut_gerer_utilisateurs=self.cleaned_data.get('peut_gerer_utilisateurs', False),
        )
        return user
