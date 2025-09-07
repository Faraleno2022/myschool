from django.core.management.base import BaseCommand
from notes.models import BaremeMatiere

BASE_SUBJECTS = [
    "Mathématiques",
    "Physique-Chimie",
    "SVT",
    "Français",
    "Philosophie",
    "Anglais",
    "Histoire-Géographie",
    "Informatique",
    "EPS",
]

PRESET = {
    # Sciences Sociales (orientation littéraire et sciences humaines)
    "L12SS": {
        "Mathématiques": 3,
        "Physique-Chimie": 2,
        "SVT": 2,
        "Français": 5,
        "Philosophie": 5,
        "Anglais": 3,
        "Histoire-Géographie": 4,
        "Informatique": 2,
        "EPS": 1,
    },
    # Sciences Mathématiques (orientation maths/physique)
    "L12SM": {
        "Mathématiques": 7,
        "Physique-Chimie": 6,
        "SVT": 3,
        "Français": 4,
        "Philosophie": 3,
        "Anglais": 2,
        "Histoire-Géographie": 2,
        "Informatique": 2,
        "EPS": 1,
    },
    # Sciences Expérimentales (orientation PC/SVT)
    "L12SE": {
        "Mathématiques": 5,
        "Physique-Chimie": 6,
        "SVT": 5,
        "Français": 4,
        "Philosophie": 2,
        "Anglais": 2,
        "Histoire-Géographie": 2,
        "Informatique": 2,
        "EPS": 1,
    },
}


class Command(BaseCommand):
    help = "Pré-remplit un barème GLOBAL (toutes écoles, toutes années) pour L12SS/L12SM/L12SE."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for serie, mapping in PRESET.items():
            for matiere in BASE_SUBJECTS:
                coef = mapping[matiere]
                obj, was_created = BaremeMatiere.objects.get_or_create(
                    ecole=None,
                    annee_scolaire=None,
                    code_serie=serie,
                    nom_matiere=matiere,
                    defaults={"coefficient": coef, "actif": True},
                )
                if was_created:
                    created += 1
                else:
                    if obj.coefficient != coef or not obj.actif:
                        obj.coefficient = coef
                        obj.actif = True
                        obj.save(update_fields=["coefficient", "actif"])
                        updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"Barèmes 12e (Global) — créés: {created}, mis à jour: {updated}"
        ))
