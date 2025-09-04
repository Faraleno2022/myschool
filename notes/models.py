from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from eleves.models import Classe, Ecole


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
