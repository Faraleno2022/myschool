import os
import sys
import django
from datetime import date
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Ecole, GrilleTarifaire


def current_academic_year() -> str:
    today = date.today()
    y = today.year
    if today.month >= 9:
        return f"{y}-{y+1}"
    return f"{y-1}-{y}"

def resolve_target_year() -> str:
    """Resolve target academic year from CLI arg or env, else current."""
    # CLI arg precedence
    if len(sys.argv) >= 2 and sys.argv[1]:
        return sys.argv[1]
    # Env var
    env_year = os.environ.get('TARGET_ACADEMIC_YEAR')
    if env_year:
        return env_year
    # Fallback
    return current_academic_year()


def upsert_grille(ecole: Ecole, niveau: str, annee: str, frais_inscription: int, t1: int, t2: int, t3: int):
    grille, created = GrilleTarifaire.objects.get_or_create(
        ecole=ecole, niveau=niveau, annee_scolaire=annee,
        defaults={
            'frais_inscription': Decimal(frais_inscription),
            'tranche_1': Decimal(t1),
            'tranche_2': Decimal(t2),
            'tranche_3': Decimal(t3),
        }
    )
    if not created:
        grille.frais_inscription = Decimal(frais_inscription)
        grille.tranche_1 = Decimal(t1)
        grille.tranche_2 = Decimal(t2)
        grille.tranche_3 = Decimal(t3)
        grille.save()
    return grille, created


def main():
    annee = resolve_target_year()

    # Try to find or create schools by name
    sonfonia, _ = Ecole.objects.get_or_create(
        nom='GROUPE SCOLAIRE myschool DE SONFONIA',
        defaults={
            'adresse': 'Sonfonia',
            'telephone': '+224000000000',
            'directeur': 'Directeur',
        }
    )
    somayah, _ = Ecole.objects.get_or_create(
        nom='GROUPE SCOLAIRE myschool DE SOMAYAH',
        defaults={
            'adresse': 'Somayah',
            'telephone': '+224000000001',
            'directeur': 'Directeur',
        }
    )

    # SONFONIA: Inscription 50_000 GNF

    # Amounts table
    # Garderie: 2_800_000 total -> tranches: 1_200_000 / 900_000 / 700_000
    son_garderie = (1_200_000, 900_000, 700_000)
    # Maternelle: 2_000_000 -> 900_000 / 700_000 / 400_000
    son_maternelle = (900_000, 700_000, 400_000)
    # Primaire 1-4: 1_700_000 -> 800_000 / 500_000 / 400_000
    son_pri_1_4 = (800_000, 500_000, 400_000)
    # Primaire 5-6: 2_000_000 -> 900_000 / 700_000 / 400_000
    son_pri_5_6 = (900_000, 700_000, 400_000)
    # Collège 7-8: 2_100_000 -> 900_000 / 700_000 / 500_000
    son_col_7_8 = (900_000, 700_000, 500_000)
    # Collège 9-10: 2_300_000 -> 1_000_000 / 800_000 / 500_000
    son_col_9_10 = (1_000_000, 800_000, 500_000)
    # Lycée 11: 2_200_000 -> 1_000_000 / 700_000 / 500_000
    son_lyc_11 = (1_000_000, 700_000, 500_000)
    # Lycée 12: 2_400_000 -> 1_200_000 / 700_000 / 500_000
    son_lyc_12 = (1_200_000, 700_000, 500_000)
    # Terminales: 2_800_000 -> 1_500_000 / 800_000 / 500_000
    son_term = (1_500_000, 800_000, 500_000)

    # Map to Classe.NIVEAUX_CHOICES codes
    niveaux = {
        'GARDERIE': son_garderie,
        'MATERNELLE': son_maternelle,
        'PRIMAIRE_1': son_pri_1_4,
        'PRIMAIRE_2': son_pri_1_4,
        'PRIMAIRE_3': son_pri_1_4,
        'PRIMAIRE_4': son_pri_1_4,
        'PRIMAIRE_5': son_pri_5_6,
        'PRIMAIRE_6': son_pri_5_6,
        'COLLEGE_7': son_col_7_8,
        'COLLEGE_8': son_col_7_8,
        'COLLEGE_9': son_col_9_10,
        'COLLEGE_10': son_col_9_10,
        'LYCEE_11': son_lyc_11,
        'LYCEE_12': son_lyc_12,
        'TERMINALE': son_term,
    }

    for niveau_code, (t1, t2, t3) in niveaux.items():
        upsert_grille(sonfonia, niveau_code, annee, 50_000, t1, t2, t3)

    # SOMAYAH: Inscription 30_000 GNF

    # Maternelle: 650_000 / 500_000 / 350_000 -> total 1_500_000
    som_maternelle = (650_000, 500_000, 350_000)
    # Primaire 1-5: 560_000 / 460_000 / 330_000 -> total 1_350_000
    som_pri_1_5 = (560_000, 460_000, 330_000)
    # Primaire 6: 710_000 / 610_000 / 480_000 -> total 1_800_000
    som_pri_6 = (710_000, 610_000, 480_000)
    # Collège 7-9: 660_000 / 660_000 / 300_000 -> total 1_620_000
    som_col_7_9 = (660_000, 660_000, 300_000)
    # Collège 10: 710_000 / 610_000 / 480_000 -> total 1_800_000
    som_col_10 = (710_000, 610_000, 480_000)
    # Lycée 11-12: 760_000 / 590_000 / 360_000 -> total 1_710_000
    som_lyc_11_12 = (760_000, 590_000, 360_000)

    niveaux_som = {
        'MATERNELLE': som_maternelle,
        'PRIMAIRE_1': som_pri_1_5,
        'PRIMAIRE_2': som_pri_1_5,
        'PRIMAIRE_3': som_pri_1_5,
        'PRIMAIRE_4': som_pri_1_5,
        'PRIMAIRE_5': som_pri_1_5,
        'PRIMAIRE_6': som_pri_6,
        'COLLEGE_7': som_col_7_9,
        'COLLEGE_8': som_col_7_9,
        'COLLEGE_9': som_col_7_9,
        'COLLEGE_10': som_col_10,
        'LYCEE_11': som_lyc_11_12,
        'LYCEE_12': som_lyc_11_12,
    }

    for niveau_code, (t1, t2, t3) in niveaux_som.items():
        upsert_grille(somayah, niveau_code, annee, 30_000, t1, t2, t3)

    print(f"Grilles tarifaires chargées/mises à jour pour l'année {annee}.")


if __name__ == '__main__':
    main()
