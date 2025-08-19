from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from decimal import Decimal

class Ecole(models.Model):
    """Modèle pour représenter une école"""
    nom = models.CharField(max_length=200, verbose_name="Nom de l'école")
    adresse = models.TextField(verbose_name="Adresse")
    telephone = models.CharField(
        max_length=20, 
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone"
    )
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    directeur = models.CharField(max_length=100, verbose_name="Directeur")
    logo = models.ImageField(upload_to='ecoles/logos/', blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "École"
        verbose_name_plural = "Écoles"
    
    def __str__(self):
        return self.nom

class Classe(models.Model):
    """Modèle pour représenter une classe"""
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
    
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='classes')
    nom = models.CharField(max_length=100, verbose_name="Nom de la classe")
    niveau = models.CharField(max_length=20, choices=NIVEAUX_CHOICES, verbose_name="Niveau")
    annee_scolaire = models.CharField(max_length=9, verbose_name="Année scolaire", help_text="Format: 2024-2025")
    capacite_max = models.PositiveIntegerField(default=30, verbose_name="Capacité maximale")
    
    class Meta:
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        unique_together = ['ecole', 'nom', 'annee_scolaire']
        indexes = [
            models.Index(fields=['ecole', 'niveau']),
            models.Index(fields=['ecole', 'annee_scolaire']),
        ]
    
    def __str__(self):
        return f"{self.nom} - {self.get_niveau_display()} ({self.annee_scolaire})"
    
    @property
    def nombre_eleves(self):
        return self.eleves.count()

class Responsable(models.Model):
    """Modèle pour représenter un responsable d'élève"""
    RELATION_CHOICES = [
        ('PERE', 'Père'),
        ('MERE', 'Mère'),
        ('TUTEUR', 'Tuteur'),
        ('TUTRICE', 'Tutrice'),
        ('GRAND_PERE', 'Grand-père'),
        ('GRAND_MERE', 'Grand-mère'),
        ('ONCLE', 'Oncle'),
        ('TANTE', 'Tante'),
        ('AUTRE', 'Autre'),
    ]
    
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    relation = models.CharField(max_length=20, choices=RELATION_CHOICES, verbose_name="Relation")
    telephone = models.CharField(
        max_length=20, 
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone"
    )
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    adresse = models.TextField(verbose_name="Adresse")
    profession = models.CharField(max_length=100, blank=True, null=True, verbose_name="Profession")
    
    class Meta:
        verbose_name = "Responsable"
        verbose_name_plural = "Responsables"
    
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.get_relation_display()})"

    @property
    def nom_complet(self) -> str:
        """Retourne le nom complet du responsable (Prénom Nom)."""
        return f"{self.prenom} {self.nom}"

class GrilleTarifaire(models.Model):
    """Modèle pour les grilles tarifaires par école et niveau"""
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='grilles_tarifaires')
    niveau = models.CharField(max_length=20, choices=Classe.NIVEAUX_CHOICES, verbose_name="Niveau")
    annee_scolaire = models.CharField(max_length=9, verbose_name="Année scolaire")
    
    # Frais d'inscription
    frais_inscription = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Frais d'inscription (GNF)"
    )
    
    # Frais de scolarité par tranches
    tranche_1 = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="1ère tranche (GNF)"
    )
    tranche_2 = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="2ème tranche (GNF)"
    )
    tranche_3 = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="3ème tranche (GNF)"
    )
    
    # Périodes de paiement
    periode_1 = models.CharField(max_length=50, default="À l'inscription", verbose_name="Période 1")
    periode_2 = models.CharField(max_length=50, default="Début janvier", verbose_name="Période 2")
    periode_3 = models.CharField(max_length=50, default="Début mars", verbose_name="Période 3")
    
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Grille tarifaire"
        verbose_name_plural = "Grilles tarifaires"
        unique_together = ['ecole', 'niveau', 'annee_scolaire']
    
    def __str__(self):
        return f"{self.ecole.nom} - {self.get_niveau_display()} ({self.annee_scolaire})"
    
    @property
    def total_scolarite(self):
        return self.tranche_1 + self.tranche_2 + self.tranche_3
    
    @property
    def total_avec_inscription(self):
        return self.frais_inscription + self.total_scolarite

class Eleve(models.Model):
    """Modèle principal pour représenter un élève"""
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'),
        ('EXCLU', 'Exclu'),
        ('TRANSFERE', 'Transféré'),
        ('DIPLOME', 'Diplômé'),
    ]
    
    # Informations personnelles
    matricule = models.CharField(max_length=20, unique=True, verbose_name="Matricule")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, verbose_name="Sexe")
    date_naissance = models.DateField(verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=100, verbose_name="Lieu de naissance")
    photo = models.ImageField(upload_to='eleves/photos/', blank=True, null=True, verbose_name="Photo")
    
    # Scolarité
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='eleves')
    date_inscription = models.DateField(verbose_name="Date d'inscription")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF', verbose_name="Statut", db_index=True)
    
    # Responsables
    responsable_principal = models.ForeignKey(
        Responsable, on_delete=models.CASCADE, 
        related_name='eleves_principal', verbose_name="Responsable principal"
    )
    responsable_secondaire = models.ForeignKey(
        Responsable, on_delete=models.SET_NULL, 
        related_name='eleves_secondaire', blank=True, null=True,
        verbose_name="Responsable secondaire"
    )
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Élève"
        verbose_name_plural = "Élèves"
        ordering = ['nom', 'prenom']
        indexes = [
            models.Index(fields=['classe', 'statut']),
            models.Index(fields=['nom', 'prenom']),
            models.Index(fields=['date_inscription']),
        ]
    
    def __str__(self):
        return f"{self.matricule} - {self.prenom} {self.nom}"
    
    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"
    
    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_naissance.year - ((today.month, today.day) < (self.date_naissance.month, self.date_naissance.day))

class HistoriqueEleve(models.Model):
    """Modèle pour l'historique des modifications d'un élève"""
    ACTION_CHOICES = [
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('CHANGEMENT_CLASSE', 'Changement de classe'),
        ('CHANGEMENT_STATUT', 'Changement de statut'),
        ('SUSPENSION', 'Suspension'),
        ('EXCLUSION', 'Exclusion'),
        ('TRANSFERT', 'Transfert'),
    ]
    
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='historique')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Action")
    description = models.TextField(verbose_name="Description")
    date_action = models.DateTimeField(auto_now_add=True, verbose_name="Date de l'action")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Historique élève"
        verbose_name_plural = "Historiques élèves"
        ordering = ['-date_action']
    
    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.get_action_display()} ({self.date_action.strftime('%d/%m/%Y')})"

