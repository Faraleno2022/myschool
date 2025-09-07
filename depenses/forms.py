from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import (
    Depense, CategorieDepense, Fournisseur, 
    PieceJustificative, BudgetAnnuel
)

class DepenseForm(forms.ModelForm):
    """Formulaire simplifié pour les dépenses"""
    
    class Meta:
        model = Depense
        fields = ['date_facture', 'description', 'montant_ht']
        widgets = {
            'date_facture': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Date de la dépense'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description de la dépense'
            }),
            'montant_ht': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '0',
                'placeholder': 'Montant en GNF'
            }),
        }
        labels = {
            'date_facture': 'Date',
            'description': 'Description',
            'montant_ht': 'Montant (GNF)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre tous les champs obligatoires
        self.fields['date_facture'].required = True
        self.fields['description'].required = True
        self.fields['montant_ht'].required = True

    def clean_montant_ht(self):
        montant_ht = self.cleaned_data.get('montant_ht')
        if montant_ht and montant_ht <= 0:
            raise ValidationError("Le montant doit être supérieur à 0.")
        return montant_ht

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Définir des valeurs par défaut pour les champs non inclus dans le formulaire
        if not instance.numero_facture:
            # Générer un numéro de facture automatique
            from datetime import datetime
            now = datetime.now()
            instance.numero_facture = f"DEP-{now.strftime('%Y%m%d-%H%M%S')}"
        
        if not instance.libelle:
            # Utiliser les 50 premiers caractères de la description comme libellé
            instance.libelle = instance.description[:50] if instance.description else "Dépense"
        
        # Créer ou récupérer une catégorie par défaut
        if not hasattr(instance, 'categorie') or not instance.categorie_id:
            categorie_defaut, created = CategorieDepense.objects.get_or_create(
                code='GENERAL',
                defaults={
                    'nom': 'Dépenses générales',
                    'description': 'Catégorie par défaut pour les dépenses',
                    'actif': True
                }
            )
            instance.categorie = categorie_defaut
        
        # Créer ou récupérer un fournisseur par défaut
        if not hasattr(instance, 'fournisseur') or not instance.fournisseur_id:
            fournisseur_defaut, created = Fournisseur.objects.get_or_create(
                nom='Fournisseur général',
                defaults={
                    'type_fournisseur': 'ENTREPRISE',
                    'adresse': 'Adresse non spécifiée',
                    'telephone': '000000000',
                    'actif': True
                }
            )
            instance.fournisseur = fournisseur_defaut
        
        # Valeurs par défaut
        instance.statut = 'VALIDEE'  # Statut par défaut
        instance.taux_tva = Decimal('0')  # Pas de TVA par défaut
        instance.date_echeance = instance.date_facture  # Même date que la facture
        instance.type_depense = 'FONCTIONNEMENT'  # Type par défaut
        
        if commit:
            instance.save()
        return instance

class CategorieDepenseForm(forms.ModelForm):
    """Formulaire pour les catégories de dépenses"""
    
    class Meta:
        model = CategorieDepense
        fields = ['nom', 'description', 'code', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la catégorie'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description de la catégorie'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code (ex: FONC, INV, PERS)'
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
            # Vérifier l'unicité du code
            if self.instance.pk:
                if CategorieDepense.objects.exclude(pk=self.instance.pk).filter(code=code).exists():
                    raise ValidationError("Ce code existe déjà.")
            else:
                if CategorieDepense.objects.filter(code=code).exists():
                    raise ValidationError("Ce code existe déjà.")
        return code

class FournisseurForm(forms.ModelForm):
    """Formulaire pour les fournisseurs"""
    
    class Meta:
        model = Fournisseur
        fields = [
            'nom', 'type_fournisseur', 'adresse', 'telephone', 'email',
            'numero_compte', 'banque', 'numero_nif', 'numero_rccm', 'actif'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du fournisseur'
            }),
            'type_fournisseur': forms.Select(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adresse complète'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de téléphone'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse email'
            }),
            'numero_compte': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de compte bancaire'
            }),
            'banque': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la banque'
            }),
            'numero_nif': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro NIF'
            }),
            'numero_rccm': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro RCCM'
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if telephone:
            # Supprimer les espaces et caractères spéciaux
            telephone = ''.join(filter(str.isdigit, telephone))
            if len(telephone) < 8:
                raise ValidationError("Le numéro de téléphone doit contenir au moins 8 chiffres.")
        return telephone

class PieceJustificativeForm(forms.ModelForm):
    """Formulaire pour les pièces justificatives"""
    
    class Meta:
        model = PieceJustificative
        fields = ['type_piece', 'nom_fichier', 'fichier', 'description']
        widgets = {
            'type_piece': forms.Select(attrs={'class': 'form-control'}),
            'nom_fichier': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du fichier'
            }),
            'fichier': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Description du document'
            }),
        }

    def clean_fichier(self):
        fichier = self.cleaned_data.get('fichier')
        if fichier:
            # Vérifier la taille du fichier (max 10MB)
            if fichier.size > 10 * 1024 * 1024:
                raise ValidationError("La taille du fichier ne doit pas dépasser 10 MB.")
            
            # Vérifier l'extension
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            file_extension = fichier.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError("Format de fichier non autorisé. Formats acceptés: PDF, JPG, PNG, DOC, DOCX.")
        
        return fichier

class BudgetAnnuelForm(forms.ModelForm):
    """Formulaire pour le budget annuel"""
    
    class Meta:
        model = BudgetAnnuel
        fields = ['annee', 'categorie', 'budget_prevu']
        widgets = {
            'annee': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2020',
                'max': '2030',
                'placeholder': 'Année'
            }),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'budget_prevu': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '0',
                'placeholder': 'Budget prévu en GNF'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categorie'].queryset = CategorieDepense.objects.filter(actif=True)

    def clean_budget_prevu(self):
        budget_prevu = self.cleaned_data.get('budget_prevu')
        if budget_prevu and budget_prevu <= 0:
            raise ValidationError("Le budget prévu doit être supérieur à 0.")
        return budget_prevu

    def clean(self):
        cleaned_data = super().clean()
        annee = cleaned_data.get('annee')
        categorie = cleaned_data.get('categorie')
        
        if annee and categorie:
            # Vérifier qu'il n'existe pas déjà un budget pour cette année et catégorie
            if self.instance.pk:
                existing = BudgetAnnuel.objects.exclude(pk=self.instance.pk).filter(
                    annee=annee, categorie=categorie
                )
            else:
                existing = BudgetAnnuel.objects.filter(annee=annee, categorie=categorie)
            
            if existing.exists():
                raise ValidationError("Un budget existe déjà pour cette catégorie et cette année.")
        
        return cleaned_data

class RechercheDepenseForm(forms.Form):
    """Formulaire de recherche pour les dépenses"""
    
    recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par libellé, numéro de facture...'
        })
    )
    
    statut = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous les statuts')] + Depense.STATUT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    categorie = forms.ModelChoiceField(
        required=False,
        queryset=CategorieDepense.objects.filter(actif=True),
        empty_label="Toutes les catégories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    fournisseur = forms.ModelChoiceField(
        required=False,
        queryset=Fournisseur.objects.filter(actif=True),
        empty_label="Tous les fournisseurs",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        
        if date_debut and date_fin:
            if date_fin < date_debut:
                raise ValidationError("La date de fin ne peut pas être antérieure à la date de début.")
        
        return cleaned_data
