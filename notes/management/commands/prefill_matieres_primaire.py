from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from eleves.models import Classe
from notes.models import MatiereClasse

PRIMAIRE_LEVELS = {
    'PRIMAIRE_1', 'PRIMAIRE_2', 'PRIMAIRE_3', 'PRIMAIRE_4', 'PRIMAIRE_5', 'PRIMAIRE_6'
}

# Matières et coefficients par défaut pour le primaire
DEFAULT_MATIERES = [
    ("Français", 4),
    ("Mathématiques", 4),
    ("Lecture", 2),
    ("Écriture", 2),
    ("Sciences", 2),
    ("Histoire-Géographie", 2),
    ("Éducation civique", 1),
    ("Anglais", 2),
    ("Informatique", 1),
    ("Dessin", 1),
    ("Musique", 1),
    ("Sport", 1),
]


class Command(BaseCommand):
    help = "Pré-remplit les matières par défaut pour toutes les classes du primaire (PRIMAIRE_1..6)."

    def add_arguments(self, parser):
        parser.add_argument("--classe", type=int, dest="classe_id", help="ID d'une classe à traiter uniquement")
        parser.add_argument("--ecole", type=int, dest="ecole_id", help="ID d'une école à restreindre")
        parser.add_argument("--dry-run", action="store_true", help="Simuler sans enregistrer")

    @transaction.atomic
    def handle(self, *args, **options):
        classe_id = options.get("classe_id")
        ecole_id = options.get("ecole_id")
        dry_run = options.get("dry_run")

        qs = Classe.objects.select_related("ecole")
        if classe_id:
            qs = qs.filter(id=classe_id)
        else:
            qs = qs.filter(niveau__in=PRIMAIRE_LEVELS)
        if ecole_id:
            qs = qs.filter(ecole_id=ecole_id)

        total_classes = qs.count()
        created_total = 0
        skipped_total = 0

        if total_classes == 0:
            self.stdout.write(self.style.WARNING("Aucune classe primaire trouvée avec ces critères."))
            return

        self.stdout.write(self.style.NOTICE(f"Traitement de {total_classes} classe(s) primaire(s)"))

        for classe in qs:
            for nom, coef in DEFAULT_MATIERES:
                exists = MatiereClasse.objects.filter(ecole=classe.ecole, classe=classe, nom=nom).exists()
                if exists:
                    skipped_total += 1
                    continue
                if dry_run:
                    created_total += 1
                    continue
                MatiereClasse.objects.create(
                    ecole=classe.ecole,
                    classe=classe,
                    nom=nom,
                    coefficient=coef,
                    actif=True,
                )
                created_total += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[DRY-RUN] Créations possibles: {created_total}, déjà existantes: {skipped_total}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Matières primaire pré-remplies. Créées: {created_total}, déjà existantes: {skipped_total}"
            ))
