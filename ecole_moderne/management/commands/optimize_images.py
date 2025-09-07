"""
Commande Django pour optimiser les images de l'application
Usage: python manage.py optimize_images
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os
import sys

# Ajouter le répertoire parent au path pour importer image_optimization
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from PIL import Image
    from ecole_moderne.image_optimization import ImageOptimizer, optimize_static_images
except ImportError as e:
    print(f"Erreur d'import: {e}")
    print("Assurez-vous que Pillow est installé avec: pip install Pillow")
    ImageOptimizer = None

class Command(BaseCommand):
    help = 'Optimise toutes les images de l\'application pour améliorer les performances'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['static', 'eleves', 'all'],
            default='all',
            help='Type d\'images à optimiser (static, eleves, ou all)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['WEBP', 'JPEG'],
            default='WEBP',
            help='Format de sortie pour les images optimisées'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans effectuer les modifications'
        )

    def handle(self, *args, **options):
        if not ImageOptimizer:
            self.stdout.write(
                self.style.ERROR('Pillow n\'est pas installé. Installez-le avec: pip install Pillow')
            )
            return

        image_type = options['type']
        output_format = options['format']
        dry_run = options['dry_run']

        self.stdout.write(
            self.style.SUCCESS(f'🚀 Optimisation des images ({image_type}) en format {output_format}')
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('Mode DRY-RUN activé - aucune modification ne sera effectuée'))

        total_original_size = 0
        total_optimized_size = 0
        processed_count = 0

        # Optimiser les images statiques
        if image_type in ['static', 'all']:
            self.stdout.write('\n📁 Traitement des images statiques...')
            original_size, optimized_size, count = self._optimize_static_images(output_format, dry_run)
            total_original_size += original_size
            total_optimized_size += optimized_size
            processed_count += count

        # Optimiser les photos d'élèves
        if image_type in ['eleves', 'all']:
            self.stdout.write('\n👥 Traitement des photos d\'élèves...')
            original_size, optimized_size, count = self._optimize_eleve_photos(output_format, dry_run)
            total_original_size += original_size
            total_optimized_size += optimized_size
            processed_count += count

        # Afficher le résumé
        if processed_count > 0:
            reduction_percent = round((1 - total_optimized_size / total_original_size) * 100, 1) if total_original_size > 0 else 0
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Optimisation terminée!\n'
                    f'   📊 {processed_count} images traitées\n'
                    f'   📉 Taille originale: {round(total_original_size / (1024*1024), 2)} MB\n'
                    f'   📈 Taille optimisée: {round(total_optimized_size / (1024*1024), 2)} MB\n'
                    f'   🎯 Réduction: {reduction_percent}%'
                )
            )
        else:
            self.stdout.write(self.style.WARNING('Aucune image à traiter trouvée.'))

    def _optimize_static_images(self, output_format, dry_run):
        """Optimise les images dans static/images/"""
        static_images_dir = os.path.join(settings.BASE_DIR, 'static', 'images')
        optimized_dir = os.path.join(static_images_dir, 'optimized')
        
        if not os.path.exists(static_images_dir):
            self.stdout.write(self.style.WARNING('Répertoire static/images non trouvé'))
            return 0, 0, 0

        total_original = 0
        total_optimized = 0
        count = 0

        # Créer le répertoire optimized si nécessaire
        if not dry_run:
            os.makedirs(optimized_dir, exist_ok=True)

        for filename in os.listdir(static_images_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(static_images_dir, filename)
                
                # Obtenir les infos de l'image originale
                info = ImageOptimizer.get_image_info(image_path)
                original_size = info.get('size_bytes', 0)
                total_original += original_size
                
                self.stdout.write(f'   📸 {filename} ({info.get("size_mb", 0)} MB)')

                if not dry_run:
                    # Créer les versions optimisées
                    versions = ImageOptimizer.create_responsive_versions(image_path, optimized_dir)
                    
                    # Calculer la taille totale des versions optimisées
                    version_size = 0
                    for size_type, optimized_path in versions.items():
                        if os.path.exists(optimized_path):
                            opt_info = ImageOptimizer.get_image_info(optimized_path)
                            version_size += opt_info.get('size_bytes', 0)
                            reduction = round((1 - opt_info.get('size_mb', 0) / info.get('size_mb', 1)) * 100, 1)
                            self.stdout.write(f'      ✅ {size_type}: {opt_info.get("size_mb", 0)} MB (-{reduction}%)')
                    
                    total_optimized += version_size
                else:
                    # En mode dry-run, estimer la réduction
                    estimated_optimized = original_size * 0.3  # Estimation 70% de réduction
                    total_optimized += estimated_optimized
                    self.stdout.write(f'      🔍 Estimation: ~{round(estimated_optimized/(1024*1024), 2)} MB')

                count += 1

        return total_original, total_optimized, count

    def _optimize_eleve_photos(self, output_format, dry_run):
        """Optimise les photos d'élèves"""
        eleves_photos_dir = os.path.join(settings.BASE_DIR, 'eleves', 'photos')
        optimized_dir = os.path.join(eleves_photos_dir, 'optimized')
        
        if not os.path.exists(eleves_photos_dir):
            self.stdout.write(self.style.WARNING('Répertoire eleves/photos non trouvé'))
            return 0, 0, 0

        total_original = 0
        total_optimized = 0
        count = 0

        # Créer le répertoire optimized si nécessaire
        if not dry_run:
            os.makedirs(optimized_dir, exist_ok=True)

        for filename in os.listdir(eleves_photos_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(eleves_photos_dir, filename)
                
                # Obtenir les infos de l'image originale
                info = ImageOptimizer.get_image_info(image_path)
                original_size = info.get('size_bytes', 0)
                total_original += original_size
                
                self.stdout.write(f'   👤 {filename} ({info.get("size_mb", 0)} MB)')

                if not dry_run:
                    # Pour les photos d'élèves, créer seulement thumbnail et small
                    base_name = os.path.splitext(filename)[0]
                    
                    # Version thumbnail (pour listes)
                    thumb_path = os.path.join(optimized_dir, f"{base_name}_thumbnail.webp")
                    ImageOptimizer.optimize_image(image_path, thumb_path, 'thumbnail', output_format)
                    
                    # Version small (pour détails)
                    small_path = os.path.join(optimized_dir, f"{base_name}_small.webp")
                    ImageOptimizer.optimize_image(image_path, small_path, 'small', output_format)
                    
                    # Calculer les tailles
                    thumb_size = os.path.getsize(thumb_path) if os.path.exists(thumb_path) else 0
                    small_size = os.path.getsize(small_path) if os.path.exists(small_path) else 0
                    version_size = thumb_size + small_size
                    
                    total_optimized += version_size
                    
                    reduction = round((1 - version_size / original_size) * 100, 1) if original_size > 0 else 0
                    self.stdout.write(f'      ✅ Optimisé: {round(version_size/(1024*1024), 3)} MB (-{reduction}%)')
                else:
                    # En mode dry-run, estimer la réduction
                    estimated_optimized = original_size * 0.2  # Estimation 80% de réduction pour photos
                    total_optimized += estimated_optimized
                    self.stdout.write(f'      🔍 Estimation: ~{round(estimated_optimized/(1024*1024), 3)} MB')

                count += 1

        return total_original, total_optimized, count
