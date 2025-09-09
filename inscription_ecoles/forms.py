from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import DemandeInscriptionEcole, ConfigurationEcole, TemplateDocument, ClasseInscription, EcheancierInscription
from eleves.models import Ecole
from datetime import date, datetime
from decimal import Decimal


class DemandeInscriptionForm(forms.ModelForm):
    """Formulaire pour la demande d'inscription d'une école"""
    
    class Meta:
        model = DemandeInscriptionEcole
        fields = [
            'nom_demandeur', 'prenom_demandeur', 'fonction_demandeur',
            'email_demandeur', 'telephone_demandeur',
            'nom_ecole', 'nom_complet_ecole', 'type_ecole',
            'adresse_ecole', 'ville', 'prefecture',
            'telephone_ecole', 'email_ecole', 'site_web',
            'nom_directeur', 'telephone_directeur',
            'numero_autorisation', 'date_autorisation',
            'logo_ecole', 'document_autorisation', 'autres_documents',
            'nombre_eleves_estime', 'nombre_enseignants', 'niveaux_enseignes',
            'commentaire_demandeur'
        ]
        widgets = {
            'nom_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre nom'}),
            'prenom_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre prénom'}),
            'fonction_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Directeur, Propriétaire...'}),
            'email_demandeur': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'votre.email@exemple.com'}),
            'telephone_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+224XXXXXXXXX'}),
            
            'nom_ecole': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de votre école'}),
            'nom_complet_ecole': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet officiel (optionnel)'}),
            'type_ecole': forms.Select(attrs={'class': 'form-control'}),
            
            'adresse_ecole': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse complète de l\'école'}),
            'ville': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville'}),
            'prefecture': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Préfecture'}),
            
            'telephone_ecole': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+224XXXXXXXXX'}),
            'email_ecole': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@ecole.com'}),
            'site_web': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.ecole.com (optionnel)'}),
            
            'nom_directeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet du directeur'}),
            'telephone_directeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+224XXXXXXXXX (optionnel)'}),
            
            'numero_autorisation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro d\'autorisation (optionnel)'}),
            'date_autorisation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            
            'logo_ecole': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'document_autorisation': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
            'autres_documents': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.jpg,.png'}),
            
            'nombre_eleves_estime': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Nombre d\'élèves'}),
            'nombre_enseignants': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Nombre d\'enseignants'}),
            'niveaux_enseignes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ex: Maternelle, Primaire (CP-CM2), Collège (6ème-3ème)...'}),
            
            'commentaire_demandeur': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Informations complémentaires (optionnel)'}),
        }


class ConfigurationEcoleForm(forms.ModelForm):
    """Formulaire pour la configuration d'une école"""
    
    class Meta:
        model = ConfigurationEcole
        fields = [
            'en_tete_personnalise', 'pied_page_personnalise',
            'afficher_logo_documents', 'taille_logo_documents',
            'prefixe_recu', 'prefixe_facture',
            'email_notifications', 'sms_notifications'
        ]
        widgets = {
            'en_tete_personnalise': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'Texte d\'en-tête pour les documents (optionnel)'
            }),
            'pied_page_personnalise': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Texte de pied de page pour les documents (optionnel)'
            }),
            'afficher_logo_documents': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'taille_logo_documents': forms.Select(attrs={'class': 'form-control'}),
            'prefixe_recu': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'REC', 'maxlength': '10'}),
            'prefixe_facture': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FAC', 'maxlength': '10'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TemplateDocumentForm(forms.ModelForm):
    """Formulaire pour créer/modifier un template de document"""
    
    class Meta:
        model = TemplateDocument
        fields = ['nom', 'type_document', 'contenu_html', 'styles_css', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du template'}),
            'type_document': forms.Select(attrs={'class': 'form-control'}),
            'contenu_html': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 15, 
                'placeholder': 'Contenu HTML du document...'
            }),
            'styles_css': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 10, 
                'placeholder': 'Styles CSS (optionnel)...'
            }),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class EcoleUpdateForm(forms.ModelForm):
    """Formulaire pour mettre à jour les informations d'une école"""
    
    class Meta:
        model = Ecole
        fields = [
            'nom', 'nom_complet', 'type_ecole',
            'adresse', 'ville', 'prefecture',
            'telephone', 'telephone_2', 'email', 'site_web',
            'directeur', 'directeur_telephone', 'directeur_email',
            'logo', 'couleur_principale', 'couleur_secondaire',
            'numero_autorisation', 'date_autorisation', 'ministere_tutelle',
            'devise', 'fuseau_horaire', 'langue_principale'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'nom_complet': forms.TextInput(attrs={'class': 'form-control'}),
            'type_ecole': forms.Select(attrs={'class': 'form-control'}),
            
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'prefecture': forms.TextInput(attrs={'class': 'form-control'}),
            
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_2': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'site_web': forms.URLInput(attrs={'class': 'form-control'}),
            
            'directeur': forms.TextInput(attrs={'class': 'form-control'}),
            'directeur_telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'directeur_email': forms.EmailInput(attrs={'class': 'form-control'}),
            
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'couleur_principale': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'couleur_secondaire': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            
            'numero_autorisation': forms.TextInput(attrs={'class': 'form-control'}),
            'date_autorisation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ministere_tutelle': forms.TextInput(attrs={'class': 'form-control'}),
            
            'devise': forms.TextInput(attrs={'class': 'form-control'}),
            'fuseau_horaire': forms.TextInput(attrs={'class': 'form-control'}),
            'langue_principale': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ClasseInscriptionForm(forms.ModelForm):
    """Formulaire pour ajouter une classe lors de l'inscription"""
    
    class Meta:
        model = ClasseInscription
        fields = [
            'nom', 'niveau', 'code_matricule', 'capacite_max',
            'frais_inscription', 'tranche_1', 'tranche_2', 'tranche_3'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ex: CP1, CE1A, 6ème A...'
            }),
            'niveau': forms.Select(attrs={'class': 'form-control'}),
            'code_matricule': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ex: CP1, CE1, 6A...',
                'maxlength': '12'
            }),
            'capacite_max': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '1', 
                'max': '100',
                'value': '30'
            }),
            'frais_inscription': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0',
                'step': '1000',
                'placeholder': '0'
            }),
            'tranche_1': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0',
                'step': '1000',
                'placeholder': '0'
            }),
            'tranche_2': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0',
                'step': '1000',
                'placeholder': '0'
            }),
            'tranche_3': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0',
                'step': '1000',
                'placeholder': '0'
            }),
        }
    
    def clean_frais_inscription(self):
        value = self.cleaned_data.get('frais_inscription')
        if value and value < 0:
            raise forms.ValidationError("Les frais d'inscription ne peuvent pas être négatifs.")
        return value
    
    def clean_tranche_1(self):
        value = self.cleaned_data.get('tranche_1')
        if value and value < 0:
            raise forms.ValidationError("Le montant de la tranche ne peut pas être négatif.")
        return value
    
    def clean_tranche_2(self):
        value = self.cleaned_data.get('tranche_2')
        if value and value < 0:
            raise forms.ValidationError("Le montant de la tranche ne peut pas être négatif.")
        return value
    
    def clean_tranche_3(self):
        value = self.cleaned_data.get('tranche_3')
        if value and value < 0:
            raise forms.ValidationError("Le montant de la tranche ne peut pas être négatif.")
        return value


class EcheancierInscriptionForm(forms.ModelForm):
    """Formulaire pour définir les échéances lors de l'inscription"""
    
    class Meta:
        model = EcheancierInscription
        fields = [
            'annee_scolaire', 'date_echeance_inscription', 'date_echeance_tranche_1',
            'date_echeance_tranche_2', 'date_echeance_tranche_3', 
            'autoriser_paiement_partiel', 'penalite_retard'
        ]
        widgets = {
            'annee_scolaire': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '2024-2025',
                'pattern': r'\d{4}-\d{4}'
            }),
            'date_echeance_inscription': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'date_echeance_tranche_1': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'date_echeance_tranche_2': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'date_echeance_tranche_3': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'autoriser_paiement_partiel': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'penalite_retard': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0',
                'max': '100',
                'step': '0.1',
                'placeholder': '0.0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajouter des classes CSS Bootstrap pour un meilleur rendu
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
            
            # Marquer les champs requis
            if field.required:
                field.widget.attrs['required'] = True
        
        # Définir l'année scolaire par défaut
        if not self.instance.pk:
            current_year = datetime.now().year
            if datetime.now().month >= 9:  # Année scolaire commence en septembre
                annee_debut = current_year
            else:
                annee_debut = current_year - 1
            self.fields['annee_scolaire'].initial = f"{annee_debut}-{annee_debut + 1}"
            
            # Dates par défaut
            today = date.today()
            self.fields['date_echeance_inscription'].initial = today
            
            # Échéances par défaut (basées sur l'année scolaire)
            try:
                if datetime.now().month >= 9:
                    # Premier trimestre: janvier
                    self.fields['date_echeance_tranche_1'].initial = date(annee_debut + 1, 1, 15)
                    # Deuxième trimestre: mars  
                    self.fields['date_echeance_tranche_2'].initial = date(annee_debut + 1, 3, 15)
                    # Troisième trimestre: mai
                    self.fields['date_echeance_tranche_3'].initial = date(annee_debut + 1, 5, 15)
                else:
                    # Si on est déjà dans l'année scolaire en cours
                    self.fields['date_echeance_tranche_1'].initial = date(current_year, 1, 15)
                    self.fields['date_echeance_tranche_2'].initial = date(current_year, 3, 15)
                    self.fields['date_echeance_tranche_3'].initial = date(current_year, 5, 15)
            except:
                pass  # En cas d'erreur, laisser les champs vides
    
    def clean_annee_scolaire(self):
        value = self.cleaned_data.get('annee_scolaire')
        if value:
            # Vérifier le format YYYY-YYYY
            import re
            if not re.match(r'^\d{4}-\d{4}$', value):
                raise forms.ValidationError("Format attendu: YYYY-YYYY (ex: 2024-2025)")
            
            # Vérifier que les années sont consécutives
            try:
                annee1, annee2 = value.split('-')
                if int(annee2) != int(annee1) + 1:
                    raise forms.ValidationError("Les années doivent être consécutives (ex: 2024-2025)")
            except ValueError:
                raise forms.ValidationError("Format d'année invalide")
        return value
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Vérifier que les dates d'échéance sont cohérentes
        date_inscription = cleaned_data.get('date_echeance_inscription')
        date_tranche_1 = cleaned_data.get('date_echeance_tranche_1')
        date_tranche_2 = cleaned_data.get('date_echeance_tranche_2')
        date_tranche_3 = cleaned_data.get('date_echeance_tranche_3')
        
        dates = [date_inscription, date_tranche_1, date_tranche_2, date_tranche_3]
        dates_valides = [d for d in dates if d is not None]
        
        if len(dates_valides) > 1:
            dates_triees = sorted(dates_valides)
            if dates_valides != dates_triees:
                raise forms.ValidationError(
                    "Les dates d'échéance doivent être dans l'ordre chronologique."
                )
        
        return cleaned_data


# Formsets pour gérer plusieurs classes
ClasseInscriptionFormSet = inlineformset_factory(
    DemandeInscriptionEcole,
    ClasseInscription,
    form=ClasseInscriptionForm,
    extra=3,  # 3 formulaires vides par défaut
    min_num=1,  # Au moins une classe requise
    validate_min=True,
    can_delete=True
)


class DemandeInscriptionCompleteForm(forms.ModelForm):
    """Formulaire complet pour la demande d'inscription avec classes et échéances"""
    
    class Meta:
        model = DemandeInscriptionEcole
        fields = [
            'nom_demandeur', 'prenom_demandeur', 'fonction_demandeur',
            'email_demandeur', 'telephone_demandeur',
            'nom_ecole', 'nom_complet_ecole', 'type_ecole',
            'adresse_ecole', 'ville', 'prefecture',
            'telephone_ecole', 'email_ecole', 'site_web',
            'nom_directeur', 'telephone_directeur',
            'numero_autorisation', 'date_autorisation',
            'logo_ecole', 'document_autorisation', 'autres_documents',
            'nombre_eleves_estime', 'nombre_enseignants', 'niveaux_enseignes',
            'commentaire_demandeur'
        ]
        widgets = {
            'nom_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre nom'}),
            'prenom_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre prénom'}),
            'fonction_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Directeur, Propriétaire...'}),
            'email_demandeur': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'votre.email@exemple.com'}),
            'telephone_demandeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+224XXXXXXXXX'}),
            
            'nom_ecole': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de votre école'}),
            'nom_complet_ecole': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet officiel (optionnel)'}),
            'type_ecole': forms.Select(attrs={'class': 'form-control'}),
            
            'adresse_ecole': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse complète de l\'école'}),
            'ville': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville'}),
            'prefecture': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Préfecture'}),
            
            'telephone_ecole': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+224XXXXXXXXX'}),
            'email_ecole': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@ecole.com'}),
            'site_web': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.ecole.com (optionnel)'}),
            
            'nom_directeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet du directeur'}),
            'telephone_directeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+224XXXXXXXXX (optionnel)'}),
            
            'numero_autorisation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro d\'autorisation (optionnel)'}),
            'date_autorisation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            
            'logo_ecole': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'document_autorisation': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
            'autres_documents': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.jpg,.png'}),
            
            'nombre_eleves_estime': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Nombre d\'élèves'}),
            'nombre_enseignants': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Nombre d\'enseignants'}),
            'niveaux_enseignes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ex: Maternelle, Primaire (CP-CM2), Collège (6ème-3ème)...'}),
            
            'commentaire_demandeur': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Informations complémentaires (optionnel)'}),
        }
