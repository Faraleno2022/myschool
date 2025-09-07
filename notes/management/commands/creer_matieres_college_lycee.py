from django.core.management.base import BaseCommand
from django.db import transaction
from typing import Dict, List, Tuple
from eleves.models import Ecole, Classe
from notes.models import MatiereClasse, BaremeMatiere

# Types
SubjectDef = Tuple[str, int]  # (nom, coefficient)

# Matières et coefficients par défaut pour le Collège (CN7 à CN10)
COLLEGE_SUBJECTS: List[SubjectDef] = [
    ("Mathématiques", 4),
    ("Physique-Chimie", 3),
    ("SVT", 2),
    ("Français", 4),
    ("Anglais", 3),
    ("Histoire-Géographie", 2),
    ("Education Civique et Morale", 1),
    ("Informatique", 1),
    ("EPS", 1),
]

# Lycée 11e: séries Littéraire / Scientifique I / Scientifique II
LYCEE_11_SL: List[SubjectDef] = [
    ("Français", 5),
    ("Philosophie", 4),
    ("Histoire-Géographie", 3),
    ("Anglais", 3),
    ("Mathématiques", 2),
    ("Physique-Chimie", 1),
    ("SVT", 1),
    ("Informatique", 1),
    ("EPS", 1),
]

LYCEE_11_SS: List[SubjectDef] = [
    ("Mathématiques", 5),
    ("Physique-Chimie", 4),
    ("SVT", 3),
    ("Français", 3),
    ("Anglais", 2),
    ("Histoire-Géographie", 2),
    ("Philosophie", 2),
    ("Informatique", 1),
    ("EPS", 1),
]

# Lycée 12e: séries SS / SM / SE (coefficients proches, adaptables)
LYCEE_12_SCI: List[SubjectDef] = [
    ("Mathématiques", 5),
    ("Physique-Chimie", 4),
    ("SVT", 3),
    ("Français", 3),
    ("Philosophie", 2),
    ("Anglais", 2),
    ("Histoire-Géographie", 2),
    ("Informatique", 1),
    ("EPS", 1),
]

# Terminale: TSS / TSM / TSE (par défaut: profil scientifique)
TERMINALE_SCI: List[SubjectDef] = [
    ("Mathématiques", 6),
    ("Physique-Chimie", 5),
    ("SVT", 4),
    ("Français", 3),
    ("Philosophie", 2),
    ("Anglais", 2),
    ("Histoire-Géographie", 2),
    ("Informatique", 1),
    ("EPS", 1),
]


def subjects_for_classe(classe: Classe) -> List[SubjectDef]:
    """Retourne la liste des matières par défaut en fonction du niveau/série de la classe.
    Utilise `code_matricule` et `niveau`/`nom` comme fallback.
    """
    code = (classe.code_matricule or "").upper()
    niveau = (classe.niveau or "").upper()
    nom = (classe.nom or "").lower()

    # Collège
    if niveau in {"COLLEGE_7", "COLLEGE_8", "COLLEGE_9", "COLLEGE_10"}:
        return COLLEGE_SUBJECTS
    if code.startswith("CN"):
        return COLLEGE_SUBJECTS

    # Lycée 11e séries
    if code.startswith("L11SL") or "litt" in nom:
        return LYCEE_11_SL
    if code.startswith("L11SS") or "scientifique" in nom:
        return LYCEE_11_SS
    if niveau == "LYCEE_11":
        # Sans précision: par défaut scientifique
        return LYCEE_11_SS

    # Lycée 12e séries (SS/SM/SE traitées pareil par défaut)
    if code.startswith("L12") or niveau == "LYCEE_12":
        return LYCEE_12_SCI

    # Terminale (TSS/TSM/TSE)
    if code.startswith("TS") or niveau == "TERMINALE" or "term" in nom:
        return TERMINALE_SCI

    # Fallback vide (pas de création par défaut)
    return []


def detect_serie_code(classe: Classe) -> str:
    """Détecte un code de série standardisé pour recherche de barème.
    Retourne par ex: 'COLLEGE', 'L11SL', 'L11SS', 'L11SSII', 'L12SS', 'L12SM', 'L12SE', 'TERMINALE'.
    """
    code = (classe.code_matricule or "").upper()
    niveau = (classe.niveau or "").upper()
    nom = (classe.nom or "").lower()

    if niveau in {"COLLEGE_7", "COLLEGE_8", "COLLEGE_9", "COLLEGE_10"} or code.startswith("CN"):
        return "COLLEGE"

    if niveau == "LYCEE_11" or code.startswith("L11"):
        if code.startswith("L11SL") or "litt" in nom:
            return "L11SL"
        if code.startswith("L11SSII"):
            return "L11SSII"
        # défaut scientifique
        return "L11SS"

    if niveau == "LYCEE_12" or code.startswith("L12"):
        if code.startswith("L12SS"):
            return "L12SS"
        if code.startswith("L12SM"):
            return "L12SM"
        if code.startswith("L12SE"):
            return "L12SE"
        # défaut scientifique générique
        return "L12SS"

    if niveau == "TERMINALE" or code.startswith("TS") or "term" in nom:
        if code.startswith("TSS"):
            return "TSS"
        if code.startswith("TSM"):
            return "TSM"
        if code.startswith("TSE"):
            return "TSE"
        return "TERMINALE"

    return ""


def ensure_subjects_for_classe(ecole: Ecole, classe: Classe, update: bool = False) -> int:
    """Crée les matières manquantes pour une classe. Si update=True, met aussi à jour
    les coefficients existants pour correspondre aux valeurs par défaut.
    Retourne le nombre de matières créées.
    """
    created = 0
    defaults = subjects_for_classe(classe)

    # Appliquer barèmes: priorité du plus spécifique au plus générique
    serie = detect_serie_code(classe)
    annee = getattr(classe, "annee_scolaire", None)

    override_map = {}
    if serie:
        # 1) ecole + annee
        for b in BaremeMatiere.objects.filter(ecole=ecole, annee_scolaire=annee, code_serie=serie, actif=True):
            override_map[b.nom_matiere] = b.coefficient
        # 2) ecole, toutes années
        for b in BaremeMatiere.objects.filter(ecole=ecole, annee_scolaire__isnull=True, code_serie=serie, actif=True):
            override_map.setdefault(b.nom_matiere, b.coefficient)
        # 3) global + annee
        for b in BaremeMatiere.objects.filter(ecole__isnull=True, annee_scolaire=annee, code_serie=serie, actif=True):
            override_map.setdefault(b.nom_matiere, b.coefficient)
        # 4) global, toutes années
        for b in BaremeMatiere.objects.filter(ecole__isnull=True, annee_scolaire__isnull=True, code_serie=serie, actif=True):
            override_map.setdefault(b.nom_matiere, b.coefficient)

    for nom, coef in defaults:
        if nom in override_map:
            coef = override_map[nom]
        obj, was_created = MatiereClasse.objects.get_or_create(
            ecole=ecole,
            classe=classe,
            nom=nom,
            defaults={"coefficient": coef, "actif": True},
        )
        if was_created:
            created += 1
        else:
            if update and obj.coefficient != coef:
                obj.coefficient = coef
                obj.save(update_fields=["coefficient"])
    return created


class Command(BaseCommand):
    help = (
        "Crée un jeu de matières avec coefficients pour les classes du Collège et du Lycée.\n"
        "Par défaut: crée seulement les matières manquantes. Utiliser --update pour mettre à jour les coefficients.\n"
        "Usage: python manage.py creer_matieres_college_lycee [--annee 2025-2026] [--ecole 'Nom'] [--update]"
    )

    def add_arguments(self, parser):
        parser.add_argument("--annee", type=str, help="Filtre sur l'année scolaire (ex: 2025-2026). Si absent, toutes années.")
        parser.add_argument("--ecole", type=str, help="Nom exact de l'école. Si absent, toutes les écoles.")
        parser.add_argument("--update", action="store_true", help="Met à jour les coefficients existants selon les valeurs par défaut.")

    @transaction.atomic
    def handle(self, *args, **options):
        annee = options.get("annee")
        ecole_nom = options.get("ecole")
        update = options.get("update", False)

        ecoles_qs = Ecole.objects.all()
        if ecole_nom:
            ecoles_qs = ecoles_qs.filter(nom=ecole_nom)
            if not ecoles_qs.exists():
                self.stdout.write(self.style.ERROR(f"Aucune école trouvée avec le nom: {ecole_nom}"))
                return

        total_created = 0
        for ecole in ecoles_qs:
            classes_qs = ecole.classes.all()
            if annee:
                classes_qs = classes_qs.filter(annee_scolaire=annee)
            # Cible uniquement collège/lycée/terminale
            classes_qs = classes_qs.filter(niveau__in=[
                "COLLEGE_7", "COLLEGE_8", "COLLEGE_9", "COLLEGE_10",
                "LYCEE_11", "LYCEE_12", "TERMINALE",
            ])

            created_for_ecole = 0
            for classe in classes_qs:
                created_for_ecole += ensure_subjects_for_classe(ecole, classe, update=update)

            total_created += created_for_ecole
            self.stdout.write(self.style.SUCCESS(
                f"École: {ecole.nom} — Matières créées: {created_for_ecole}"
            ))

        self.stdout.write(self.style.SUCCESS(f"Total matières créées: {total_created}"))
