from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from eleves.models import Eleve

class TypePaiement(models.Model):
    """Modèle pour les types de paiements"""
    nom = models.CharField(max_length=100, unique=True, verbose_name="Nom du type")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    class Meta:
        verbose_name = "Type de paiement"
        verbose_name_plural = "Types de paiements"
    
    def __str__(self):
        return self.nom

class ModePaiement(models.Model):
    """Modèle pour les modes de paiements"""
    nom = models.CharField(max_length=100, unique=True, verbose_name="Nom du mode")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    frais_supplementaires = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Frais supplémentaires (GNF)"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    class Meta:
        verbose_name = "Mode de paiement"
        verbose_name_plural = "Modes de paiements"
    
    def __str__(self):
        return self.nom

class Paiement(models.Model):
    """Modèle principal pour les paiements"""
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Validé'),
        ('REJETE', 'Rejeté'),
        ('REMBOURSE', 'Remboursé'),
    ]
    
    # Références
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='paiements')
    type_paiement = models.ForeignKey(TypePaiement, on_delete=models.CASCADE)
    mode_paiement = models.ForeignKey(ModePaiement, on_delete=models.CASCADE)
    
    # Informations du paiement
    numero_recu = models.CharField(max_length=20, unique=True, verbose_name="Numéro de reçu")
    montant = models.DecimalField(
        max_digits=10, decimal_places=0,
        verbose_name="Montant (GNF)"
    )
    date_paiement = models.DateField(verbose_name="Date de paiement")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE', verbose_name="Statut")
    
    # Informations complémentaires
    reference_externe = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Référence externe",
        help_text="Numéro de transaction Mobile Money, chèque, etc."
    )
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paiements_crees'
    )
    valide_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paiements_valides'
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    
    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-date_paiement', '-date_creation']
    
    def __str__(self):
        return f"{self.numero_recu} - {self.eleve.nom_complet} - {self.montant:,.0f} GNF"
    
    @property
    def montant_avec_frais(self):
        return self.montant + self.mode_paiement.frais_supplementaires

class EcheancierPaiement(models.Model):
    """Modèle pour l'échéancier des paiements d'un élève"""
    STATUT_CHOICES = [
        ('A_PAYER', 'À payer'),
        ('PAYE_PARTIEL', 'Payé partiellement'),
        ('PAYE_COMPLET', 'Payé complètement'),
        ('EN_RETARD', 'En retard'),
    ]
    
    eleve = models.OneToOneField(Eleve, on_delete=models.CASCADE, related_name='echeancier')
    annee_scolaire = models.CharField(max_length=9, verbose_name="Année scolaire")
    
    # Montants dus
    frais_inscription_du = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Frais d'inscription dus (GNF)"
    )
    tranche_1_due = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="1ère tranche due (GNF)"
    )
    tranche_2_due = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="2ème tranche due (GNF)"
    )
    tranche_3_due = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="3ème tranche due (GNF)"
    )
    
    # Dates d'échéance
    date_echeance_inscription = models.DateField(verbose_name="Échéance inscription")
    date_echeance_tranche_1 = models.DateField(verbose_name="Échéance 1ère tranche")
    date_echeance_tranche_2 = models.DateField(verbose_name="Échéance 2ème tranche")
    date_echeance_tranche_3 = models.DateField(verbose_name="Échéance 3ème tranche")
    
    # Montants payés
    frais_inscription_paye = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Frais d'inscription payés (GNF)"
    )
    tranche_1_payee = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="1ère tranche payée (GNF)"
    )
    tranche_2_payee = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="2ème tranche payée (GNF)"
    )
    tranche_3_payee = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="3ème tranche payée (GNF)"
    )
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='A_PAYER', verbose_name="Statut")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Échéancier de paiement"
        verbose_name_plural = "Échéanciers de paiements"
    
    def __str__(self):
        return f"Échéancier {self.eleve.nom_complet} - {self.annee_scolaire}"
    
    @property
    def total_du(self):
        return self.frais_inscription_du + self.tranche_1_due + self.tranche_2_due + self.tranche_3_due
    
    @property
    def total_paye(self):
        return self.frais_inscription_paye + self.tranche_1_payee + self.tranche_2_payee + self.tranche_3_payee
    
    @property
    def solde_restant(self):
        return self.total_du - self.total_paye
    
    @property
    def pourcentage_paye(self):
        if self.total_du > 0:
            return (self.total_paye / self.total_du) * 100
        return 0

class RemiseReduction(models.Model):
    """Modèle pour les remises et réductions"""
    TYPE_CHOICES = [
        ('POURCENTAGE', 'Pourcentage'),
        ('MONTANT_FIXE', 'Montant fixe'),
    ]
    
    MOTIF_CHOICES = [
        ('FRATRIE', 'Réduction fratrie'),
        ('MERITE', 'Réduction mérite'),
        ('SOCIALE', 'Réduction sociale'),
        ('EMPLOYEE', 'Enfant d\'employé'),
        ('AUTRE', 'Autre'),
    ]
    
    nom = models.CharField(max_length=100, verbose_name="Nom de la remise")
    type_remise = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type de remise")
    valeur = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Valeur",
        help_text="Pourcentage (ex: 10.50) ou montant en GNF"
    )
    motif = models.CharField(max_length=20, choices=MOTIF_CHOICES, verbose_name="Motif")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    
    # Conditions d'application
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Remise/Réduction"
        verbose_name_plural = "Remises/Réductions"
    
    def __str__(self):
        if self.type_remise == 'POURCENTAGE':
            return f"{self.nom} - {self.valeur}%"
        else:
            return f"{self.nom} - {self.valeur:,.0f} GNF"
    
    def calculer_remise(self, montant_base):
        """Calcule le montant de la remise sur un montant de base"""
        if self.type_remise == 'POURCENTAGE':
            return (montant_base * self.valeur) / 100
        else:
            return min(self.valeur, montant_base)  # La remise ne peut pas être supérieure au montant

class PaiementRemise(models.Model):
    """Modèle pour associer des remises aux paiements"""
    paiement = models.ForeignKey(Paiement, on_delete=models.CASCADE, related_name='remises')
    remise = models.ForeignKey(RemiseReduction, on_delete=models.CASCADE)
    montant_remise = models.DecimalField(
        max_digits=10, decimal_places=0,
        verbose_name="Montant de la remise (GNF)"
    )
    
    class Meta:
        verbose_name = "Remise appliquée"
        verbose_name_plural = "Remises appliquées"
        unique_together = ['paiement', 'remise']
    
    def __str__(self):
        return f"{self.paiement.numero_recu} - {self.remise.nom} - {self.montant_remise:,.0f} GNF"

