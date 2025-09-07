from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from typing import List, Optional, Tuple
from eleves.models import Ecole, Classe


def current_academic_year_str(today=None) -> str:
    """Return academic year string like '2025-2026'.
    If today is before Sept 1, we consider we're still in the previous academic year.
    """
    from datetime import date
    if today is None:
        today = date.today()
    year = today.year
    sep_first = date(year, 9, 1)
    if today < sep_first:
        start = year - 1
    else:
        start = year
    return f"{start}-{start+1}"


COLLEGE_CLASSES: List[Tuple[str, str, str]] = [
    ("7ème année", "COLLEGE_7", "CN7"),
    ("8ème année", "COLLEGE_8", "CN8"),
    ("9ème année", "COLLEGE_9", "CN9"),
    ("10ème année", "COLLEGE_10", "CN10"),
]

# Lycée 11e: séries Littéraire / Scientifique I / Scientifique II
LYCEE_11_CLASSES: List[Tuple[str, str, str]] = [
    ("11ème Série Littéraire", "LYCEE_11", "L11SL"),
    ("11ème Série Scientifique I", "LYCEE_11", "L11SSI"),
    ("11ème Série Scientifique II", "LYCEE_11", "L11SSII"),
]

# Lycée 12e: SS / SM / SE
LYCEE_12_CLASSES: List[Tuple[str, str, str]] = [
    ("12ème SS", "LYCEE_12", "L12SS"),
    ("12ème SM", "LYCEE_12", "L12SM"),
    ("12ème SE", "LYCEE_12", "L12SE"),
]

# Optionnel: Terminale séries (si l'école souhaite déjà créer des terminales)
TERMINALE_CLASSES: List[Tuple[str, str, str]] = [
    ("Terminale SS", "TERMINALE", "TSS"),
    ("Terminale SM", "TERMINALE", "TSM"),
    ("Terminale SE", "TERMINALE", "TSE"),
]


def create_or_get_classes_for_ecole(ecole: Ecole, annee: str, include_terminale: bool = True) -> int:
    """Create collège and lycée classes for a school if they don't exist for the given academic year.
    Returns the number of classes created.
    """
    created = 0
    definitions = []  # (nom, niveau, code)
    definitions.extend(COLLEGE_CLASSES)
    definitions.extend(LYCEE_11_CLASSES)
    definitions.extend(LYCEE_12_CLASSES)
    if include_terminale:
        definitions.extend(TERMINALE_CLASSES)

    for nom, niveau, code in definitions:
        obj, was_created = Classe.objects.get_or_create(
            ecole=ecole,
            nom=nom,
            annee_scolaire=annee,
            defaults={
                "niveau": niveau,
                "code_matricule": code,
                "capacite_max": 30,
            },
        )
        if was_created:
            created += 1
        else:
            # Ensure fields are consistent if class exists but fields differ
            changed = False
            if obj.niveau != niveau:
                obj.niveau = niveau
                changed = True
            if not obj.code_matricule:
                obj.code_matricule = code
                changed = True
            if changed:
                obj.save(update_fields=["niveau", "code_matricule"])
    return created


class Command(BaseCommand):
    help = (
        "Crée automatiquement les classes pour le collège (CN7–CN10) et le lycée "
        "(L11 séries SL/SSI/SSII, L12 séries SS/SM/SE), et terminale (SS/SM/SE) optionnellement.\n"
        "Usage: python manage.py creer_classes_college_lycee [--annee 2025-2026] [--ecole 'Nom'] [--sans-terminale]"
    )

    def add_arguments(self, parser):
        parser.add_argument("--annee", type=str, help="Année scolaire au format 2024-2025")
        parser.add_argument(
            "--ecole",
            type=str,
            help="Nom exact de l'école pour laquelle créer les classes. Par défaut: toutes les écoles",
        )
        parser.add_argument(
            "--sans-terminale",
            action="store_true",
            help="Ne pas créer les classes terminales (TSS/TSM/TSE)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        annee = options.get("annee") or current_academic_year_str()
        ecole_nom = options.get("ecole")
        include_terminale = not options.get("sans_terminale")

        if ecole_nom:
            ecoles = Ecole.objects.filter(nom=ecole_nom)
            if not ecoles.exists():
                self.stdout.write(self.style.ERROR(f"Aucune école trouvée avec le nom: {ecole_nom}"))
                return
        else:
            ecoles = Ecole.objects.all()
            if not ecoles.exists():
                self.stdout.write(self.style.WARNING("Aucune école dans la base. Création impossible."))
                return

        total_created = 0
        for ecole in ecoles:
            created = create_or_get_classes_for_ecole(ecole, annee, include_terminale=include_terminale)
            total_created += created
            self.stdout.write(
                self.style.SUCCESS(
                    f"École: {ecole.nom} — {created} classe(s) créée(s) pour {annee}"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Total classes créées: {total_created}"))
