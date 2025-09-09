from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from decimal import Decimal

class Ecole(models.Model):
    """Modèle pour représenter une école dans un système multi-tenant"""
    STATUT_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDUE', 'Suspendue'),
        ('EN_ATTENTE', 'En attente de validation'),
        ('FERMEE', 'Fermée'),
    ]
    
    TYPE_ECOLE_CHOICES = [
        ('PUBLIQUE', 'École Publique'),
        ('PRIVEE', 'École Privée'),
        ('CONFESSIONNELLE', 'École Confessionnelle'),
        ('INTERNATIONALE', 'École Internationale'),
    ]
    
    # Informations de base
    nom = models.CharField(max_length=200, verbose_name="Nom de l'école")
    nom_complet = models.CharField(max_length=300, verbose_name="Nom complet officiel", blank=True, null=True)
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Identifiant URL", default="ecole-default")
    type_ecole = models.CharField(max_length=20, choices=TYPE_ECOLE_CHOICES, default='PRIVEE', verbose_name="Type d'école")
    
    # Contact et localisation
    adresse = models.TextField(verbose_name="Adresse")
    ville = models.CharField(max_length=100, verbose_name="Ville", default="Conakry")
    prefecture = models.CharField(max_length=100, verbose_name="Préfecture", default="Conakry")
    telephone = models.CharField(
        max_length=20, 
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone"
    )
    telephone_2 = models.CharField(
        max_length=20, 
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone 2",
        blank=True, null=True
    )
    email = models.EmailField(verbose_name="Email officiel", default="contact@ecole.com")
    site_web = models.URLField(blank=True, null=True, verbose_name="Site web")
    
    # Direction et administration
    directeur = models.CharField(max_length=100, verbose_name="Directeur/Directrice")
    directeur_telephone = models.CharField(
        max_length=20, 
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone directeur",
        blank=True, null=True
    )
    directeur_email = models.EmailField(blank=True, null=True, verbose_name="Email directeur")
    
    # Identité visuelle et documents
    logo = models.ImageField(upload_to='ecoles/logos/', blank=True, null=True, verbose_name="Logo")
    couleur_principale = models.CharField(max_length=7, default='#1976d2', verbose_name="Couleur principale (hex)")
    couleur_secondaire = models.CharField(max_length=7, default='#424242', verbose_name="Couleur secondaire (hex)")
    
    # Informations légales
    numero_autorisation = models.CharField(max_length=100, blank=True, null=True, verbose_name="N° d'autorisation")
    date_autorisation = models.DateField(blank=True, null=True, verbose_name="Date d'autorisation")
    ministere_tutelle = models.CharField(max_length=200, default="Ministère de l'Éducation Nationale", verbose_name="Ministère de tutelle")
    
    # Gestion du compte
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE', verbose_name="Statut")
    utilisateur_admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ecole_administree', verbose_name="Administrateur principal", null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_activation = models.DateTimeField(blank=True, null=True, verbose_name="Date d'activation")
    date_expiration = models.DateField(blank=True, null=True, verbose_name="Date d'expiration")
    
    # Paramètres de personnalisation
    devise = models.CharField(max_length=10, default='GNF', verbose_name="Devise")
    fuseau_horaire = models.CharField(max_length=50, default='Africa/Conakry', verbose_name="Fuseau horaire")
    langue_principale = models.CharField(max_length=10, default='fr', verbose_name="Langue principale")
    
    # Métadonnées
    notes_admin = models.TextField(blank=True, null=True, verbose_name="Notes administratives")
    
    class Meta:
        verbose_name = "École"
        verbose_name_plural = "Écoles"
        ordering = ['nom']
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['slug']),
            models.Index(fields=['ville', 'prefecture']),
        ]
    
    def __str__(self):
        return self.nom
    
    def save(self, *args, **kwargs):
        if not self.slug or self.slug == "ecole-default":
            from django.utils.text import slugify
            import uuid
            base_slug = slugify(self.nom)
            unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
            # Vérifier l'unicité
            counter = 1
            while Ecole.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}-{counter}"
                counter += 1
            self.slug = unique_slug
        # Assurer des valeurs par défaut pour les champs requis
        if not self.ville:
            self.ville = "Conakry"
        if not self.prefecture:
            self.prefecture = "Conakry"
        super().save(*args, **kwargs)
    
    @property
    def nom_affichage(self):
        return self.nom_complet or self.nom
    
    @property
    def est_active(self):
        return self.statut == 'ACTIVE'

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
    code_matricule = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        verbose_name="Code matricule",
        help_text="Préfixe utilisé pour les matricules (ex: PN3, CN7, L11SL)."
    )
    annee_scolaire = models.CharField(max_length=9, verbose_name="Année scolaire", help_text="Format: 2024-2025")
    capacite_max = models.PositiveIntegerField(default=30, verbose_name="Capacité maximale")
    
    class Meta:
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        unique_together = ['ecole', 'nom', 'annee_scolaire']
        indexes = [
            models.Index(fields=['ecole', 'niveau']),
            models.Index(fields=['ecole', 'annee_scolaire']),
            models.Index(fields=['ecole', 'code_matricule']),
        ]
    
    def __str__(self):
        return f"{self.nom} - {self.get_niveau_display()} ({self.annee_scolaire})"
    
    @property
    def nombre_eleves(self):
        return self.eleves.count()

# --- Helper: Resolve class code for matricule generation ---
def _code_classe_from_nom_ou_niveau(classe: "Classe") -> str:
    """Retourne le code matricule à partir du nom (prioritaire) ou du niveau de la classe.
    Mapping fourni par l'utilisateur. Si aucun mapping trouvé, retourne une chaîne vide.
    """
    # 1) Si le champ dédié est renseigné, on l'utilise en priorité
    code_direct = getattr(classe, 'code_matricule', None)
    if code_direct:
        return code_direct.strip()
    # Mapping par nom exact (insensible à la casse/espaces superflus)
    mapping_nom = {
        "garderie": "GA",
        "petite section": "MPS",
        "moyen section": "MMS",
        "grande section": "MGS",
        "1ère année": "PN1",
        "2ème année": "PN2",
        "3ème année": "PN3",
        "4ème année": "PN4",
        "5ème année": "PN5",
        "6ème année": "PN6",
        "7ème année": "CN7",
        "8ème année": "CN8",
        "9ème année": "CN9",
        "10ème année": "CN10",
        "11ème série littéraire": "L11SL",
        "11ème série scientifique i": "L11SSI",
        "11ème série scientifique ii": "L11SSII",
        "12ème ss": "L12SS",
        "12ème sm": "L12SM",
        "12ème se": "L12SE",
        "terminale ss": "TSS",
        "terminale se": "TSE",
        "terminale sm": "TSM",
    }

    try:
        nom_norm = (classe.nom or "").strip().lower()
    except Exception:
        nom_norm = ""
    code = mapping_nom.get(nom_norm, "")
    if code:
        return code

    # Fallback basique sur niveau si le nom ne correspond pas
    niveau = getattr(classe, "niveau", "")
    fallback_niveau = {
        "GARDERIE": "GA",
        "PRIMAIRE_1": "PN1",
        "PRIMAIRE_2": "PN2",
        "PRIMAIRE_3": "PN3",
        "PRIMAIRE_4": "PN4",
        "PRIMAIRE_5": "PN5",
        "PRIMAIRE_6": "PN6",
        "COLLEGE_7": "CN7",
        "COLLEGE_8": "CN8",
        "COLLEGE_9": "CN9",
        "COLLEGE_10": "CN10",
        "LYCEE_11": "L11",
        "LYCEE_12": "L12",
        "TERMINALE": "T",
    }
    return fallback_niveau.get(niveau, "")

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

    def save(self, *args, **kwargs):
        """Génère automatiquement le matricule au format CODE-### si absent.
        - CODE déterminé par la classe via `_code_classe_from_nom_ou_niveau`
        - ### est une séquence à 3 chiffres, incrémentée par classe
        """
        if not self.matricule and getattr(self, 'classe_id', None):
            code = _code_classe_from_nom_ou_niveau(self.classe)
            # Fallback de sécurité pour éviter un matricule vide si le code n'est pas résolu
            if not code:
                try:
                    cls_id = getattr(self.classe, 'id', None) or 'X'
                except Exception:
                    cls_id = 'X'
                code = f"CL{cls_id}"
            if code:
                import re
                base_prefix = f"{code}-"
                # Récupérer le dernier numéro pour ce préfixe
                derniers = (
                    Eleve.objects
                    .filter(matricule__startswith=base_prefix)
                    .order_by('-matricule')
                )
                next_num = 1
                if derniers.exists():
                    dernier = derniers.first().matricule
                    m = re.search(r"^(?:" + re.escape(code) + r")-(\d+)$", dernier)
                    if m:
                        try:
                            next_num = int(m.group(1)) + 1
                        except Exception:
                            next_num = 1
                # Essayer quelques fois pour éviter collision rare
                for _ in range(5):
                    candidat = f"{code}-{next_num:03d}"
                    if not Eleve.objects.filter(matricule=candidat).exists():
                        self.matricule = candidat
                        break
                    next_num += 1

        super().save(*args, **kwargs)

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
