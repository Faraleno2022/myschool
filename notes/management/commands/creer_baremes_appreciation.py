from django.core.management.base import BaseCommand
from notes.models import BaremeAppreciation, SeuilAppreciation
from eleves.models import Ecole


class Command(BaseCommand):
    help = 'Crée des barèmes d\'appréciation par défaut'

    def handle(self, *args, **options):
        self.stdout.write("🎯 Création des barèmes d'appréciation...")
        
        # Créer le barème global
        self.creer_bareme_global()
        
        # Créer les barèmes par école
        self.creer_baremes_ecoles()
        
        self.stdout.write(self.style.SUCCESS("\n✅ Barèmes d'appréciation créés avec succès!"))
        self.stdout.write("\nVous pouvez maintenant:")
        self.stdout.write("1. Aller dans l'admin Django → Notes → Barèmes d'appréciation")
        self.stdout.write("2. Modifier les seuils selon vos besoins")
        self.stdout.write("3. Créer des barèmes personnalisés pour chaque école")

    def creer_bareme_global(self):
        """Crée un barème d'appréciation global par défaut."""
        bareme, created = BaremeAppreciation.objects.get_or_create(
            ecole=None,
            nom="Barème Standard",
            defaults={
                'description': "Barème d'appréciation standard utilisé par défaut",
                'actif': True
            }
        )
        
        if created:
            self.stdout.write(f"✓ Barème global créé: {bareme}")
            
            # Créer les seuils d'appréciation
            seuils = [
                (18, "Excellent", "#28a745"),
                (16, "Très bien", "#17a2b8"),
                (14, "Bien", "#007bff"),
                (12, "Assez bien", "#ffc107"),
                (10, "Passable", "#fd7e14"),
                (8, "Médiocre", "#dc3545"),
                (0, "Insuffisant", "#6c757d"),
            ]
            
            for i, (note_min, appreciation, couleur) in enumerate(seuils):
                SeuilAppreciation.objects.create(
                    bareme=bareme,
                    note_min=note_min,
                    appreciation=appreciation,
                    couleur=couleur,
                    ordre=i,
                    actif=True
                )
                self.stdout.write(f"  ✓ Seuil créé: {note_min}+ → {appreciation}")
        else:
            self.stdout.write(f"ℹ Barème global existe déjà: {bareme}")

    def creer_baremes_ecoles(self):
        """Crée des barèmes spécifiques pour chaque école."""
        ecoles = Ecole.objects.all()
        
        for ecole in ecoles:
            bareme, created = BaremeAppreciation.objects.get_or_create(
                ecole=ecole,
                nom=f"Barème {ecole.nom}",
                defaults={
                    'description': f"Barème d'appréciation spécifique à {ecole.nom}",
                    'actif': True
                }
            )
            
            if created:
                self.stdout.write(f"✓ Barème école créé: {bareme}")
                
                # Seuils adaptés au contexte guinéen
                seuils = [
                    (17, "Excellent", "#28a745"),
                    (15, "Très bien", "#17a2b8"),
                    (13, "Bien", "#007bff"),
                    (11, "Assez bien", "#ffc107"),
                    (10, "Passable", "#fd7e14"),
                    (8, "Faible", "#dc3545"),
                    (0, "Très faible", "#6c757d"),
                ]
                
                for i, (note_min, appreciation, couleur) in enumerate(seuils):
                    SeuilAppreciation.objects.create(
                        bareme=bareme,
                        note_min=note_min,
                        appreciation=appreciation,
                        couleur=couleur,
                        ordre=i,
                        actif=True
                    )
            else:
                self.stdout.write(f"ℹ Barème école existe déjà: {bareme}")
