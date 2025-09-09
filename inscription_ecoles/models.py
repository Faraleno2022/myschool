from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from eleves.models import Ecole
from decimal import Decimal


class DemandeInscriptionEcole(models.Model):
    """Modèle pour les demandes d'inscription d'écoles"""
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente de traitement'),
        ('EN_COURS', 'En cours de vérification'),
        ('APPROUVEE', 'Approuvée'),
        ('REJETEE', 'Rejetée'),
        ('SUSPENDUE', 'Suspendue'),
    ]
    
    # Code d'accès généré par l'administrateur système
    code_acces = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True,
        null=True,
        verbose_name="Code d'accès",
        help_text="Code généré par l'administrateur pour créer le compte"
    )
    
    # Informations du demandeur
    nom_demandeur = models.CharField(max_length=100, verbose_name="Nom du demandeur")
    prenom_demandeur = models.CharField(max_length=100, verbose_name="Prénom du demandeur")
    fonction_demandeur = models.CharField(max_length=100, verbose_name="Fonction dans l'école")
    email_demandeur = models.EmailField(verbose_name="Email du demandeur")
    telephone_demandeur = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone du demandeur"
    )
    
    # Informations de l'école
    nom_ecole = models.CharField(max_length=200, verbose_name="Nom de l'école")
    nom_complet_ecole = models.CharField(max_length=300, verbose_name="Nom complet officiel", blank=True, null=True)
    type_ecole = models.CharField(max_length=20, choices=Ecole.TYPE_ECOLE_CHOICES, verbose_name="Type d'école")
    
    # Localisation
    adresse_ecole = models.TextField(verbose_name="Adresse de l'école")
    ville = models.CharField(max_length=100, verbose_name="Ville")
    prefecture = models.CharField(max_length=100, verbose_name="Préfecture")
    
    # Contact école
    telephone_ecole = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone principal"
    )
    email_ecole = models.EmailField(verbose_name="Email officiel de l'école")
    site_web = models.URLField(blank=True, null=True, verbose_name="Site web")
    
    # Direction
    nom_directeur = models.CharField(max_length=100, verbose_name="Nom du directeur")
    telephone_directeur = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone directeur",
        blank=True, null=True
    )
    
    # Documents légaux
    numero_autorisation = models.CharField(max_length=100, blank=True, null=True, verbose_name="N° d'autorisation")
    date_autorisation = models.DateField(blank=True, null=True, verbose_name="Date d'autorisation")
    
    # Documents joints
    logo_ecole = models.ImageField(upload_to='demandes/logos/', blank=True, null=True, verbose_name="Logo de l'école")
    document_autorisation = models.FileField(upload_to='demandes/documents/', blank=True, null=True, verbose_name="Document d'autorisation")
    autres_documents = models.FileField(upload_to='demandes/documents/', blank=True, null=True, verbose_name="Autres documents")
    
    # Informations complémentaires
    nombre_eleves_estime = models.PositiveIntegerField(verbose_name="Nombre d'élèves estimé")
    nombre_enseignants = models.PositiveIntegerField(verbose_name="Nombre d'enseignants")
    niveaux_enseignes = models.TextField(verbose_name="Niveaux enseignés", help_text="Ex: Maternelle, Primaire, Collège...")
    
    # Gestion de la demande
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE', verbose_name="Statut")
    date_demande = models.DateTimeField(auto_now_add=True, verbose_name="Date de demande")
    date_traitement = models.DateTimeField(blank=True, null=True, verbose_name="Date de traitement")
    traite_par = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Traité par")
    
    # Commentaires et notes
    commentaire_demandeur = models.TextField(blank=True, null=True, verbose_name="Commentaire du demandeur")
    notes_admin = models.TextField(blank=True, null=True, verbose_name="Notes administratives")
    motif_rejet = models.TextField(blank=True, null=True, verbose_name="Motif de rejet")
    
    # École créée (si approuvée)
    ecole_creee = models.OneToOneField(Ecole, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="École créée")
    
    # Utilisateur créé par l'admin
    utilisateur_cree = models.OneToOneField(User, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Utilisateur créé", related_name="demande_inscription")
    
    class Meta:
        verbose_name = "Demande d'inscription d'école"
        verbose_name_plural = "Demandes d'inscription d'écoles"
        ordering = ['-date_demande']
    
    def __str__(self):
        return f"{self.nom_ecole} - {self.get_statut_display()}"


class ConfigurationEcole(models.Model):
    """Configuration spécifique à chaque école pour la personnalisation"""
    ecole = models.OneToOneField(Ecole, on_delete=models.CASCADE, related_name='configuration')
    
    # Personnalisation des documents PDF
    en_tete_personnalise = models.TextField(blank=True, null=True, verbose_name="En-tête personnalisé")
    pied_page_personnalise = models.TextField(blank=True, null=True, verbose_name="Pied de page personnalisé")
    
    # Templates de documents
    template_fiche_inscription = models.TextField(blank=True, null=True, verbose_name="Template fiche d'inscription")
    template_recu_paiement = models.TextField(blank=True, null=True, verbose_name="Template reçu de paiement")
    template_bulletin_notes = models.TextField(blank=True, null=True, verbose_name="Template bulletin de notes")
    template_abonnement_bus = models.TextField(blank=True, null=True, verbose_name="Template abonnement bus")
    
    # Paramètres d'affichage
    afficher_logo_documents = models.BooleanField(default=True, verbose_name="Afficher le logo sur les documents")
    taille_logo_documents = models.CharField(max_length=20, default='medium', choices=[
        ('small', 'Petit'),
        ('medium', 'Moyen'),
        ('large', 'Grand')
    ], verbose_name="Taille du logo")
    
    # Numérotation des documents
    prefixe_recu = models.CharField(max_length=10, default='REC', verbose_name="Préfixe des reçus")
    prefixe_facture = models.CharField(max_length=10, default='FAC', verbose_name="Préfixe des factures")
    compteur_recu = models.PositiveIntegerField(default=1, verbose_name="Compteur des reçus")
    compteur_facture = models.PositiveIntegerField(default=1, verbose_name="Compteur des factures")
    
    # Paramètres de notification
    email_notifications = models.BooleanField(default=True, verbose_name="Notifications par email")
    sms_notifications = models.BooleanField(default=False, verbose_name="Notifications par SMS")
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuration d'école"
        verbose_name_plural = "Configurations d'écoles"
    
    def __str__(self):
        return f"Configuration - {self.ecole.nom}"
    
    def get_prochain_numero_recu(self):
        """Génère le prochain numéro de reçu"""
        numero = f"{self.prefixe_recu}-{self.compteur_recu:06d}"
        self.compteur_recu += 1
        self.save()
        return numero
    
    def get_prochain_numero_facture(self):
        """Génère le prochain numéro de facture"""
        numero = f"{self.prefixe_facture}-{self.compteur_facture:06d}"
        self.compteur_facture += 1
        self.save()
        return numero


class TemplateDocument(models.Model):
    """Templates de documents par défaut et personnalisés"""
    TYPE_DOCUMENT_CHOICES = [
        ('FICHE_INSCRIPTION', 'Fiche d\'inscription'),
        ('RECU_PAIEMENT', 'Reçu de paiement'),
        ('BULLETIN_NOTES', 'Bulletin de notes'),
        ('ABONNEMENT_BUS', 'Abonnement bus'),
        ('CERTIFICAT_SCOLARITE', 'Certificat de scolarité'),
        ('RELEVE_NOTES', 'Relevé de notes'),
    ]
    
    nom = models.CharField(max_length=100, verbose_name="Nom du template")
    type_document = models.CharField(max_length=30, choices=TYPE_DOCUMENT_CHOICES, verbose_name="Type de document")
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, blank=True, null=True, verbose_name="École (null = template par défaut)")
    
    # Contenu du template
    contenu_html = models.TextField(verbose_name="Contenu HTML")
    styles_css = models.TextField(blank=True, null=True, verbose_name="Styles CSS")
    
    # Métadonnées
    est_actif = models.BooleanField(default=True, verbose_name="Actif")
    est_par_defaut = models.BooleanField(default=False, verbose_name="Template par défaut")
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    
    class Meta:
        verbose_name = "Template de document"
        verbose_name_plural = "Templates de documents"
        unique_together = ['type_document', 'ecole', 'est_par_defaut']
    
    def __str__(self):
        ecole_nom = self.ecole.nom if self.ecole else "Par défaut"
        return f"{self.nom} - {self.get_type_document_display()} ({ecole_nom})"


class ClasseInscription(models.Model):
    """Modèle pour définir les classes lors de l'inscription d'une école"""
    NIVEAUX_CHOICES = [
        ('GARDERIE', 'Garderie'),
        ('MATERNELLE', 'Maternelle'),
        ('PRIMAIRE_1', 'Primaire 1ère'),
        ('PRIMAIRE_2', 'Primaire 2ème'),
        ('PRIMAIRE_3', 'Primaire 3ème'),
        ('PRIMAIRE_4', 'Primaire 4ème'),
        ('PRIMAIRE_5', 'Primaire 5ème'),
        ('PRIMAIRE_6', 'Primaire 6ème'),
        ('COLLEGE_7', 'Collège 7ème'),
        ('COLLEGE_8', 'Collège 8ème'),
        ('COLLEGE_9', 'Collège 9ème'),
        ('COLLEGE_10', 'Collège 10ème'),
        ('LYCEE_11', 'Lycée 11ème'),
        ('LYCEE_12', 'Lycée 12ème'),
        ('TERMINALE', 'Terminale'),
    ]
    
    demande_inscription = models.ForeignKey(
        DemandeInscriptionEcole, 
        on_delete=models.CASCADE, 
        related_name='classes_prevues'
    )
    nom = models.CharField(max_length=100, verbose_name="Nom de la classe")
    niveau = models.CharField(max_length=20, choices=NIVEAUX_CHOICES, verbose_name="Niveau")
    code_matricule = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        verbose_name="Code matricule",
        help_text="Préfixe utilisé pour les matricules (ex: PN3, CN7, L11SL)."
    )
    capacite_max = models.PositiveIntegerField(default=30, verbose_name="Capacité maximale")
    
    # Tarification pour cette classe
    frais_inscription = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=Decimal('0'),
        verbose_name="Frais d'inscription (GNF)"
    )
    tranche_1 = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=Decimal('0'),
        verbose_name="1ère tranche (GNF)"
    )
    tranche_2 = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=Decimal('0'),
        verbose_name="2ème tranche (GNF)"
    )
    tranche_3 = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=Decimal('0'),
        verbose_name="3ème tranche (GNF)"
    )
    
    class Meta:
        verbose_name = "Classe d'inscription"
        verbose_name_plural = "Classes d'inscription"
        unique_together = ['demande_inscription', 'nom']
    
    def __str__(self):
        return f"{self.nom} - {self.get_niveau_display()}"
    
    @property
    def total_annuel(self):
        """Calcule le total annuel pour cette classe"""
        return self.frais_inscription + self.tranche_1 + self.tranche_2 + self.tranche_3


class EcheancierInscription(models.Model):
    """Modèle pour définir les échéances de paiement lors de l'inscription d'une école"""
    demande_inscription = models.OneToOneField(
        DemandeInscriptionEcole, 
        on_delete=models.CASCADE, 
        related_name='echeancier_prevu'
    )
    
    # Année scolaire de référence
    annee_scolaire = models.CharField(
        max_length=9, 
        verbose_name="Année scolaire", 
        help_text="Format: 2024-2025"
    )
    
    # Dates d'échéance par défaut pour l'école
    date_echeance_inscription = models.DateField(
        verbose_name="Échéance inscription",
        help_text="Date limite pour les frais d'inscription"
    )
    date_echeance_tranche_1 = models.DateField(
        verbose_name="Échéance 1ère tranche",
        help_text="Date limite pour la 1ère tranche"
    )
    date_echeance_tranche_2 = models.DateField(
        verbose_name="Échéance 2ème tranche",
        help_text="Date limite pour la 2ème tranche"
    )
    date_echeance_tranche_3 = models.DateField(
        verbose_name="Échéance 3ème tranche",
        help_text="Date limite pour la 3ème tranche"
    )
    
    # Options de paiement
    autoriser_paiement_partiel = models.BooleanField(
        default=True, 
        verbose_name="Autoriser les paiements partiels"
    )
    penalite_retard = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Pénalité de retard (%)",
        help_text="Pourcentage de pénalité appliqué en cas de retard"
    )
    
    class Meta:
        verbose_name = "Échéancier d'inscription"
        verbose_name_plural = "Échéanciers d'inscription"
    
    def __str__(self):
        return f"Échéancier - {self.demande_inscription.nom_ecole} ({self.annee_scolaire})"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Vérifier que les dates sont dans l'ordre chronologique
        dates = [
            self.date_echeance_inscription,
            self.date_echeance_tranche_1,
            self.date_echeance_tranche_2,
            self.date_echeance_tranche_3
        ]
        
        dates_valides = [d for d in dates if d is not None]
        if len(dates_valides) > 1:
            dates_triees = sorted(dates_valides)
            if dates_valides != dates_triees:
                raise ValidationError(
                    "Les dates d'échéance doivent être dans l'ordre chronologique."
                )
