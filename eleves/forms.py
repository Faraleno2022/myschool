from django import forms
from django.core.validators import RegexValidator
from .models import Eleve, Responsable, Classe, Ecole
from datetime import date

class ResponsableForm(forms.ModelForm):
    """Formulaire pour créer/modifier un responsable"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre tous les champs optionnels au niveau du formulaire
        # La validation sera gérée manuellement dans la vue
        for field_name in self.fields:
            self.fields[field_name].required = False
        # Pré-remplir téléphone en local (8-9 chiffres) lors de la modification
        try:
            instance = getattr(self, 'instance', None)
            if instance and getattr(instance, 'pk', None):
                tel = getattr(instance, 'telephone', '') or ''
                if tel.startswith('+224'):
                    local = tel.replace('+224', '')
                    # Nettoyer pour ne garder que 8-9 derniers chiffres
                    import re
                    digits = re.sub(r'\D+', '', local)
                    self.fields['telephone'].initial = digits[-9:] if len(digits) > 9 else digits
        except Exception:
            # Ne pas bloquer le rendu du formulaire en cas d'anomalie
            pass
    
    class Meta:
        model = Responsable
        fields = ['prenom', 'nom', 'relation', 'telephone', 'email', 'adresse', 'profession']
        widgets = {
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom du responsable'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du responsable'
            }),
            'relation': forms.Select(attrs={
                'class': 'form-select'
            }),
            # Saisie locale uniquement (sans +224). Normalisation côté serveur.
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'tel',
                'inputmode': 'numeric',
                'placeholder': 'XXXXXXXXX',
                'pattern': r'^\d{8,9}$',
                'title': 'Entrez uniquement le numéro local (8 à 9 chiffres), sans +224.'
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
            'profession': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Profession (optionnel)'
            })
        }

    def clean_telephone(self):
        """Accepte une saisie locale (8-9 chiffres) et normalise en +224XXXXXXXXX.
        Si l'utilisateur fournit déjà un numéro avec indicatif, on l'accepte et on le
        normalise également.
        """
        tel = self.cleaned_data.get('telephone', '') or ''
        import re
        # Retirer tout sauf chiffres
        digits = re.sub(r'\D+', '', tel)
        if not digits:
            return ''
        # Si déjà au format international commençant par 224 et longueur 11-12
        if digits.startswith('224') and len(digits) in (11, 12):
            # Conserver les 8 ou 9 derniers chiffres comme local
            local = digits[-9:] if len(digits) == 12 else digits[-8:]
            return f'+224{local}'
        # Sinon, on attend un numéro local de 8 ou 9 chiffres
        if len(digits) not in (8, 9):
            raise forms.ValidationError("Numéro invalide. Entrez 8 à 9 chiffres sans indicatif.")
        return f'+224{digits}'

class EleveForm(forms.ModelForm):
    """Formulaire pour créer/modifier un élève"""
    
    # Champs pour les responsables
    responsable_principal_nouveau = forms.BooleanField(
        required=False,
        label="Créer un nouveau responsable principal",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    responsable_secondaire_nouveau = forms.BooleanField(
        required=False,
        label="Créer un nouveau responsable secondaire",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Eleve
        fields = [
            'matricule', 'prenom', 'nom', 'sexe', 'date_naissance', 
            'lieu_naissance', 'photo', 'classe', 'date_inscription', 
            'statut', 'responsable_principal', 'responsable_secondaire'
        ]
        widgets = {
            'matricule': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Généré automatiquement (ex: PN3-001)',
                'readonly': 'readonly'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom de l\'élève',
                'required': True
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de l\'élève',
                'required': True
            }),
            'sexe': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'date_naissance': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }, format='%Y-%m-%d'),
            'lieu_naissance': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lieu de naissance',
                'required': True
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'classe': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'date_inscription': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                # Ne pas forcer "required" en HTML pour éviter les blocages côté navigateur
            }, format='%Y-%m-%d'),
            'statut': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'responsable_principal': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'responsable_secondaire': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Définir la date d'inscription par défaut à aujourd'hui
        if not self.instance.pk:
            # En création: proposer aujourd'hui par défaut et rendre le champ requis
            self.fields['date_inscription'].initial = date.today()
            self.fields['date_inscription'].required = True
        else:
            # En modification: ne pas rendre obligatoire et garder la valeur existante
            self.fields['date_inscription'].required = False
            # Forcer la valeur initiale à celle de l'instance pour éviter les faux changements
            if self.instance.date_inscription:
                self.fields['date_inscription'].initial = self.instance.date_inscription
        
        # Filtrer les classes par école si nécessaire
        self.fields['classe'].queryset = Classe.objects.all().order_by('ecole__nom', 'niveau', 'nom')

        # Matricule: non requis et lecture seule (généré automatiquement au save())
        if 'matricule' in self.fields:
            self.fields['matricule'].required = False
            try:
                self.fields['matricule'].widget.attrs['readonly'] = 'readonly'
                self.fields['matricule'].widget.attrs['placeholder'] = 'Généré automatiquement (ex: PN3-001)'
            except Exception:
                pass

        # Rendre responsable_principal optionnel si on crée un nouveau responsable
        # La validation sera gérée dans la vue
        self.fields['responsable_principal'].required = False
        self.fields['responsable_secondaire'].required = False
        
        # Ordonner les responsables
        self.fields['responsable_principal'].queryset = Responsable.objects.all().order_by('nom', 'prenom')
        self.fields['responsable_secondaire'].queryset = Responsable.objects.all().order_by('nom', 'prenom')
        self.fields['responsable_secondaire'].required = False
    
    def clean_matricule(self):
        matricule = self.cleaned_data.get('matricule')
        if matricule:
            # Vérifier l'unicité du matricule
            qs = Eleve.objects.filter(matricule=matricule)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Ce matricule existe déjà.")
        # Autoriser vide: le modèle le générera au save()
        return matricule or ''
    
    def clean_date_naissance(self):
        date_naissance = self.cleaned_data.get('date_naissance')
        if date_naissance:
            # Vérifier que l'élève n'est pas trop jeune ou trop âgé
            age = (date.today() - date_naissance).days // 365
            if age < 2:
                raise forms.ValidationError("L'élève doit avoir au moins 2 ans.")
            if age > 25:
                raise forms.ValidationError("L'âge de l'élève semble incorrect.")
        return date_naissance

    def clean_date_inscription(self):
        """Conserver la date d'inscription existante lors d'une modification si le champ est laissé vide."""
        valeur = self.cleaned_data.get('date_inscription')
        # En création, on retourne la valeur telle quelle (la validation de required est gérée plus haut)
        if not self.instance.pk:
            return valeur
        # En modification: si vide/non fournie, on garde l'ancienne valeur pour éviter NULL
        if not valeur:
            return self.instance.date_inscription
        return valeur

class RechercheEleveForm(forms.Form):
    """Formulaire de recherche simple (zone unique multi-critères)."""
    recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher un élève...'
        })
    )

class ClasseForm(forms.ModelForm):
    """Formulaire pour créer/modifier une classe"""
    
    class Meta:
        model = Classe
        fields = ['ecole', 'nom', 'niveau', 'annee_scolaire', 'capacite_max']
        widgets = {
            'ecole': forms.Select(attrs={
                'class': 'form-select'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la classe (ex: 6ème A)'
            }),
            'niveau': forms.Select(attrs={
                'class': 'form-select'
            }),
            'annee_scolaire': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '2024-2025',
                'pattern': r'^\d{4}-\d{4}$'
            }),
            'capacite_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '50'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Définir l'année scolaire par défaut
        if not self.instance.pk:
            current_year = date.today().year
            if date.today().month >= 9:  # Année scolaire commence en septembre
                self.fields['annee_scolaire'].initial = f"{current_year}-{current_year + 1}"
            else:
                self.fields['annee_scolaire'].initial = f"{current_year - 1}-{current_year}"
    
    def clean_annee_scolaire(self):
        annee_scolaire = self.cleaned_data.get('annee_scolaire')
        if annee_scolaire:
            # Vérifier le format YYYY-YYYY
            import re
            if not re.match(r'^\d{4}-\d{4}$', annee_scolaire):
                raise forms.ValidationError("Format attendu: YYYY-YYYY (ex: 2024-2025)")
            
            # Vérifier que la deuxième année suit la première
            annees = annee_scolaire.split('-')
            if int(annees[1]) != int(annees[0]) + 1:
                raise forms.ValidationError("La deuxième année doit suivre la première (ex: 2024-2025)")
        
        return annee_scolaire
