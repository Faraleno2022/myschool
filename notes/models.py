from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from eleves.models import Classe, Ecole
from eleves.models import Eleve


class MatiereClasse(models.Model):
    """Matière définie pour une classe donnée avec un coefficient.
    - Les matières peuvent varier d'une classe à l'autre, même au sein d'un même niveau.
    - Les coefficients sont bornés (1 à 20 par défaut) mais ajustables plus tard si besoin.
    """
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='matieres_classes')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='matieres')
    nom = models.CharField(max_length=100, verbose_name="Nom de la matière")
    coefficient = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        verbose_name="Coefficient"
    )
    actif = models.BooleanField(default=True, verbose_name="Active")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Matière de classe"
        verbose_name_plural = "Matières de classe"
        unique_together = ("classe", "nom")
        indexes = [
            models.Index(fields=["ecole", "classe"]),
            models.Index(fields=["classe", "nom"]),
        ]

    def __str__(self):
        return f"{self.nom} ({self.classe})"


class BaremeMatiere(models.Model):
    """Barème configurable des matières par série/niveau.
    Permet de définir des coefficients spécifiques par école et/ou année scolaire.

    Clés principales:
    - ecole: optionnel (None = barème global)
    - annee_scolaire: optionnel (None = valable pour toutes les années)
    - code_serie: ex: 'COLLEGE', 'L11SL', 'L11SS', 'L11SSII', 'L12SS', 'L12SM', 'L12SE', 'TERMINALE'
      (On peut aussi utiliser 'CN7', 'CN8', etc., mais on recommande les grandes familles)
    - nom_matiere: ex: 'Mathématiques'
    """

    ecole = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, related_name="baremes", blank=True, null=True
    )
    annee_scolaire = models.CharField(
        max_length=9, blank=True, null=True, help_text="Format: 2025-2026 (laisser vide pour toutes années)"
    )
    code_serie = models.CharField(
        max_length=20,
        help_text="Ex: COLLEGE, L11SL, L11SS, L11SSII, L12SS, L12SM, L12SE, TERMINALE",
        db_index=True,
    )
    nom_matiere = models.CharField(max_length=100, db_index=True)
    coefficient = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(0), MaxValueValidator(40)]
    )
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Barème matière"
        verbose_name_plural = "Barèmes matières"
        unique_together = (
            ("ecole", "annee_scolaire", "code_serie", "nom_matiere"),
        )
        indexes = [
            models.Index(fields=["code_serie", "nom_matiere"]),
            models.Index(fields=["ecole", "annee_scolaire"]),
        ]

    def __str__(self):
        scope = self.ecole.nom if self.ecole else "Global"
        year = self.annee_scolaire or "Toutes années"
        return f"{scope} / {year} / {self.code_serie} — {self.nom_matiere}: {self.coefficient}"


class Evaluation(models.Model):
    """Évaluation (contrôle, devoir, examen) pour une classe et une matière.
    Permet de regrouper un ensemble de notes.
    """
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='evaluations')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='evaluations')
    matiere = models.ForeignKey(MatiereClasse, on_delete=models.CASCADE, related_name='evaluations')
    titre = models.CharField(max_length=120, verbose_name='Titre')
    date = models.DateField(blank=True, null=True)
    trimestre = models.CharField(max_length=16, blank=True, null=True, help_text="Ex: T1, T2, T3")
    coefficient = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(20)])
    annee_scolaire = models.CharField(max_length=9, blank=True, null=True, help_text="2025-2026")
    cree_par = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='evaluations_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Évaluation'
        verbose_name_plural = 'Évaluations'
        indexes = [
            models.Index(fields=['ecole', 'classe', 'matiere']),
            models.Index(fields=['annee_scolaire']),
        ]

    def __str__(self):
        return f"{self.titre} — {self.classe} / {self.matiere.nom}"


class Note(models.Model):
    """Note d'un élève pour une évaluation.
    Saisie prioritairement par matricule.
    """
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='notes')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='notes')
    matiere = models.ForeignKey(MatiereClasse, on_delete=models.CASCADE, related_name='notes')
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='notes')
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='notes')
    matricule = models.CharField(max_length=20, db_index=True)
    note = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(20)])
    observation = models.CharField(max_length=255, blank=True, null=True)
    date_saisie = models.DateTimeField(auto_now_add=True)
    saisie_par = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='notes_saisies')

    class Meta:
        verbose_name = 'Note'
        verbose_name_plural = 'Notes'
        unique_together = (('evaluation', 'eleve'),)
        indexes = [
            models.Index(fields=['ecole', 'classe', 'matiere']),
            models.Index(fields=['evaluation']),
            models.Index(fields=['matricule']),
        ]

    def get_appreciation_automatique(self):
        """Retourne l'appréciation automatique selon le barème de l'école."""
        # Chercher d'abord un barème spécifique à l'école
        bareme = BaremeAppreciation.objects.filter(
            ecole=self.ecole, actif=True
        ).first()
        
        # Si pas de barème spécifique, utiliser le barème global
        if not bareme:
            bareme = BaremeAppreciation.objects.filter(
                ecole__isnull=True, actif=True
            ).first()
        
        if bareme:
            return bareme.get_appreciation(self.note)
        
        # Barème par défaut si aucun barème configuré
        if self.note >= 16:
            return "Très bien"
        elif self.note >= 14:
            return "Bien"
        elif self.note >= 12:
            return "Assez bien"
        elif self.note >= 10:
            return "Passable"
        else:
            return "Insuffisant"

    @property
    def appreciation_finale(self):
        """Retourne l'appréciation finale : observation personnalisée ou automatique."""
        return self.observation or self.get_appreciation_automatique()

    def __str__(self):
        return f"{self.eleve.nom_complet} — {self.note}/20 ({self.evaluation.titre})"


class BaremeAppreciation(models.Model):
    """Barème d'appréciation automatique selon les notes.
    Permet de définir des seuils pour générer automatiquement des appréciations.
    """
    ecole = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, related_name="baremes_appreciation", 
        blank=True, null=True, help_text="Laisser vide pour un barème global"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom du barème")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Barème d'appréciation"
        verbose_name_plural = "Barèmes d'appréciation"
        indexes = [
            models.Index(fields=["ecole", "actif"]),
        ]

    def __str__(self):
        scope = self.ecole.nom if self.ecole else "Global"
        return f"{scope} — {self.nom}"

    def get_appreciation(self, note):
        """Retourne l'appréciation correspondant à une note selon ce barème."""
        seuils = self.seuils.filter(actif=True).order_by('-note_min')
        for seuil in seuils:
            if note >= seuil.note_min:
                return seuil.appreciation
        return "Non évalué"


class SeuilAppreciation(models.Model):
    """Seuil d'appréciation pour un barème donné.
    Ex: note >= 16 → "Très bien", note >= 14 → "Bien", etc.
    """
    bareme = models.ForeignKey(
        BaremeAppreciation, on_delete=models.CASCADE, related_name="seuils"
    )
    note_min = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name="Note minimum"
    )
    appreciation = models.CharField(max_length=100, verbose_name="Appréciation")
    couleur = models.CharField(
        max_length=7, blank=True, null=True, 
        help_text="Code couleur hex (ex: #28a745)", verbose_name="Couleur"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        verbose_name = "Seuil d'appréciation"
        verbose_name_plural = "Seuils d'appréciation"
        unique_together = (('bareme', 'note_min'),)
        ordering = ['-note_min']
        indexes = [
            models.Index(fields=["bareme", "actif", "-note_min"]),
        ]

    def __str__(self):
        return f"{self.bareme.nom} — {self.note_min}+ : {self.appreciation}"
