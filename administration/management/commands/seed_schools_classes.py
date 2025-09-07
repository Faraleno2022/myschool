from django.core.management.base import BaseCommand
from django.db import transaction

from eleves.models import Ecole, Classe, GrilleTarifaire


NIVEAUX = [
    ("GARDERIE", "Garderie"),
    ("MATERNELLE", "Maternelle"),
    ("PRIMAIRE_1", "1ère"),
    ("PRIMAIRE_2", "2ème"),
    ("PRIMAIRE_3", "3ème"),
    ("PRIMAIRE_4", "4ème"),
    ("PRIMAIRE_5", "5ème"),
    ("PRIMAIRE_6", "6ème"),
    ("COLLEGE_7", "7ème"),
    ("COLLEGE_8", "8ème"),
    ("COLLEGE_9", "9ème"),
    ("COLLEGE_10", "10ème"),
    ("LYCEE_11", "11ème"),
    ("LYCEE_12", "12ème"),
    ("TERMINALE", "Terminale"),
]

ECOLES = [
    {
        "nom": "GROUPE SCOLAIRE myschool-SOMAYAH",
        "adresse": "Somayah, Conakry",
        "telephone": "+224622000001",
        "email": "contact@somayah.school",
        "directeur": "Direction Somayah",
    },
    {
        "nom": "École Moderne myschool",
        "adresse": "Conakry",
        "telephone": "+224622000002",
        "email": "contact@moderne-hkd.gn",
        "directeur": "Direction Moderne",
    },
]


class Command(BaseCommand):
    help = "Crée les écoles et leurs classes pour une année scolaire."

    def add_arguments(self, parser):
        parser.add_argument(
            "--annee",
            default="2025-2026",
            help="Année scolaire au format AAAA-AAAA (ex: 2025-2026)",
        )
        parser.add_argument(
            "--niveaux",
            nargs="*",
            default=[code for code, _ in NIVEAUX],
            help="Filtrer les niveaux à créer (codes internes: ex COLLEGE_7, PRIMAIRE_6)",
        )
        parser.add_argument(
            "--with-grilles",
            action="store_true",
            help="Créer aussi les grilles tarifaires pour chaque niveau/école",
        )
        parser.add_argument(
            "--inscription",
            type=int,
            default=30000,
            help="Montant frais d'inscription (GNF), défaut 30000",
        )
        parser.add_argument(
            "--t1",
            type=int,
            default=660000,
            help="Montant 1ère tranche (GNF), défaut 660000",
        )
        parser.add_argument(
            "--t2",
            type=int,
            default=660000,
            help="Montant 2ème tranche (GNF), défaut 660000",
        )
        parser.add_argument(
            "--t3",
            type=int,
            default=300000,
            help="Montant 3ème tranche (GNF), défaut 300000",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        annee = options["annee"]
        niveaux_filter = set(options["niveaux"]) if options["niveaux"] else None
        with_grilles = options["with_grilles"]
        insc = options["inscription"]
        t1 = options["t1"]
        t2 = options["t2"]
        t3 = options["t3"]

        created_ecoles = 0
        created_classes = 0

        for ecole_data in ECOLES:
            ecole, e_created = Ecole.objects.get_or_create(
                nom=ecole_data["nom"],
                defaults={
                    "adresse": ecole_data["adresse"],
                    "telephone": ecole_data["telephone"],
                    "email": ecole_data["email"],
                    "directeur": ecole_data["directeur"],
                },
            )
            if e_created:
                created_ecoles += 1
                self.stdout.write(self.style.SUCCESS(f"École créée: {ecole.nom}"))
            else:
                self.stdout.write(self.style.WARNING(f"École déjà existante: {ecole.nom}"))

            for code, display in NIVEAUX:
                if niveaux_filter and code not in niveaux_filter:
                    continue
                # Nom de classe simple basé sur l'affichage
                nom_classe = display
                classe, c_created = Classe.objects.get_or_create(
                    ecole=ecole,
                    nom=nom_classe,
                    annee_scolaire=annee,
                    defaults={"niveau": code, "capacite_max": 40},
                )
                if c_created:
                    created_classes += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Classe créée: {classe.nom} - {classe.get_niveau_display()} ({classe.annee_scolaire}) pour {ecole.nom}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Classe déjà existante: {classe.nom} - {classe.get_niveau_display()} ({classe.annee_scolaire}) pour {ecole.nom}"
                    ))
                
                # Créer la grille tarifaire si demandé
                if with_grilles:
                    grille, g_created = GrilleTarifaire.objects.get_or_create(
                        ecole=ecole,
                        niveau=code,
                        annee_scolaire=annee,
                        defaults={
                            "frais_inscription": insc,
                            "tranche_1": t1,
                            "tranche_2": t2,
                            "tranche_3": t3,
                        },
                    )
                    if g_created:
                        self.stdout.write(self.style.SUCCESS(
                            f"Grille créée: {ecole.nom} - {display} ({annee}) | Inscr: {insc:,} | T1: {t1:,} | T2: {t2:,} | T3: {t3:,}"
                        ))
                    else:
                        # Si la grille existe, on peut envisager de la mettre à jour si les montants diffèrent (optionnel)
                        self.stdout.write(self.style.WARNING(
                            f"Grille déjà existante: {ecole.nom} - {display} ({annee})"
                        ))

        self.stdout.write(self.style.SUCCESS(
            f"Terminé. Écoles créées: {created_ecoles}, Classes créées: {created_classes}. Année: {annee}"
        ))
