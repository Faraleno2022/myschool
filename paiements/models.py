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
    date_paiement = models.DateField(verbose_name="Date de paiement", db_index=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE', verbose_name="Statut", db_index=True)
    
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
        indexes = [
            models.Index(fields=['eleve', 'date_paiement']),
            models.Index(fields=['eleve', 'statut']),
            models.Index(fields=['statut', 'date_paiement']),
        ]
    
    def __str__(self):
        return f"{self.numero_recu} - {self.eleve.nom_complet} - {self.montant:,.0f} GNF"
    
    def save(self, *args, **kwargs):
        """Génère automatiquement un numéro de reçu si non défini"""
        if not self.numero_recu:
            from django.utils import timezone
            from django.db import transaction, IntegrityError
            
            annee = timezone.now().year
            prefix = f"REC{annee}"
            
            # Réessayer quelques fois en cas de collision concurrente
            for _ in range(10):
                dernier = (
                    Paiement.objects
                    .filter(numero_recu__startswith=prefix)
                    .order_by('-numero_recu')
                    .first()
                )
                if dernier and isinstance(dernier.numero_recu, str) and len(dernier.numero_recu) >= 4:
                    try:
                        seq = int(dernier.numero_recu[-4:]) + 1
                    except ValueError:
                        seq = 1
                else:
                    seq = 1

                self.numero_recu = f"{prefix}{seq:04d}"
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    # Une collision est survenue, on retente avec le numéro suivant
                    continue
            else:
                # Si on n'arrive pas à générer un numéro unique après 10 tentatives
                raise ValueError("Impossible de générer un numéro de reçu unique après 10 tentatives")
        else:
            super().save(*args, **kwargs)
    
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


class Relance(models.Model):
    """Journal des relances envoyées aux responsables/élèves en retard."""
    CANAL_CHOICES = [
        ('SMS', 'SMS'),
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'E-mail'),
        ('APPEL', 'Appel téléphonique'),
        ('AUTRE', 'Autre'),
    ]
    STATUT_CHOICES = [
        ('ENREGISTREE', 'Enregistrée'),
        ('ENVOYEE', 'Envoyée'),
        ('ECHEC', 'Échec'),
    ]

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='relances')
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, default='AUTRE', verbose_name="Canal")
    message = models.TextField(verbose_name="Message de relance")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ENREGISTREE', verbose_name="Statut")
    solde_estime = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal('0'), verbose_name="Solde estimé (GNF)")

    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='relances_creees')
    date_envoi = models.DateTimeField(blank=True, null=True, verbose_name="Date d'envoi")

    class Meta:
        verbose_name = "Relance"
        verbose_name_plural = "Relances"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['eleve', 'statut']),
            models.Index(fields=['-date_creation']),
        ]

    def __str__(self):
        return f"Relance {self.eleve.nom_complet} - {self.canal} - {self.statut}"

class TwilioInboundMessage(models.Model):
    """Journalise les messages entrants Twilio (SMS/WhatsApp) et leurs statuts.
    Utilisé pour audit et debugging.
    """
    CHANNEL_CHOICES = [
        ("SMS", "SMS"),
        ("WHATSAPP", "WhatsApp"),
        ("UNKNOWN", "Inconnu"),
    ]

    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="UNKNOWN", db_index=True)
    from_number = models.CharField(max_length=50, db_index=True)
    to_number = models.CharField(max_length=50, db_index=True)
    body = models.TextField(blank=True, null=True)
    message_sid = models.CharField(max_length=64, blank=True, null=True, unique=True)
    wa_id = models.CharField(max_length=64, blank=True, null=True)
    num_media = models.IntegerField(default=0)

    # Dernier statut de livraison connu (via status callback)
    delivery_status = models.CharField(max_length=32, blank=True, null=True, db_index=True)
    error_code = models.CharField(max_length=32, blank=True, null=True)
    error_message = models.CharField(max_length=255, blank=True, null=True)
    status_updated_at = models.DateTimeField(blank=True, null=True)

    # Données brutes complètes du webhook (pratique pour debug)
    raw_data = models.JSONField(blank=True, null=True)

    # Horodatage
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Message entrant Twilio"
        verbose_name_plural = "Messages entrants Twilio"
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['message_sid']),
            models.Index(fields=['channel', 'received_at']),
        ]

    def __str__(self):
        return f"{self.channel} {self.from_number} -> {self.to_number}: {self.body[:30] if self.body else ''}"
