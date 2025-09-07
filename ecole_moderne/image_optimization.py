"""
Utilitaires d'optimisation des images pour améliorer les performances
"""
import os
from PIL import Image
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import io

class ImageOptimizer:
    """Classe pour optimiser les images et améliorer les performances"""
    
    # Tailles recommandées pour différents usages
    SIZES = {
        'thumbnail': (150, 150),
        'small': (300, 300), 
        'medium': (600, 600),
        'large': (1200, 1200),
        'hero': (1920, 1080),
    }
    
    # Qualité de compression par type
    QUALITY = {
        'thumbnail': 70,
        'small': 75,
        'medium': 80,
        'large': 85,
        'hero': 90,
    }
    
    @staticmethod
    def optimize_image(image_path, output_path=None, size_type='medium', format='WEBP'):
        """
        Optimise une image en la redimensionnant et compressant
        
        Args:
            image_path: Chemin vers l'image source
            output_path: Chemin de sortie (optionnel)
            size_type: Type de taille ('thumbnail', 'small', 'medium', 'large', 'hero')
            format: Format de sortie ('WEBP', 'JPEG', 'PNG')
        
        Returns:
            str: Chemin vers l'image optimisée
        """
        try:
            # Ouvrir l'image
            with Image.open(image_path) as img:
                # Convertir en RGB si nécessaire (pour WEBP/JPEG)
                if img.mode in ('RGBA', 'LA', 'P') and format in ('WEBP', 'JPEG'):
                    # Créer un fond blanc pour la transparence
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Redimensionner l'image
                target_size = ImageOptimizer.SIZES.get(size_type, (800, 800))
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                
                # Définir le chemin de sortie
                if not output_path:
                    base_name = os.path.splitext(image_path)[0]
                    extension = '.webp' if format == 'WEBP' else f'.{format.lower()}'
                    output_path = f"{base_name}_{size_type}{extension}"
                
                # Sauvegarder avec optimisation
                quality = ImageOptimizer.QUALITY.get(size_type, 80)
                
                if format == 'WEBP':
                    img.save(output_path, 'WEBP', quality=quality, optimize=True)
                elif format == 'JPEG':
                    img.save(output_path, 'JPEG', quality=quality, optimize=True)
                else:
                    img.save(output_path, format, optimize=True)
                
                return output_path
                
        except Exception as e:
            print(f"Erreur lors de l'optimisation de {image_path}: {e}")
            return image_path
    
    @staticmethod
    def create_responsive_versions(image_path, base_output_dir):
        """
        Crée plusieurs versions d'une image pour un affichage responsive
        
        Args:
            image_path: Chemin vers l'image source
            base_output_dir: Répertoire de base pour les versions optimisées
        
        Returns:
            dict: Dictionnaire avec les chemins des différentes versions
        """
        versions = {}
        
        for size_type in ['thumbnail', 'small', 'medium', 'large']:
            try:
                # Créer le répertoire si nécessaire
                os.makedirs(base_output_dir, exist_ok=True)
                
                # Générer le nom de fichier optimisé
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                output_file = os.path.join(base_output_dir, f"{base_name}_{size_type}.webp")
                
                # Optimiser l'image
                optimized_path = ImageOptimizer.optimize_image(
                    image_path, 
                    output_file, 
                    size_type, 
                    'WEBP'
                )
                
                versions[size_type] = optimized_path
                
            except Exception as e:
                print(f"Erreur lors de la création de la version {size_type}: {e}")
        
        return versions
    
    @staticmethod
    def get_image_info(image_path):
        """
        Récupère les informations d'une image
        
        Args:
            image_path: Chemin vers l'image
        
        Returns:
            dict: Informations sur l'image (taille, format, poids)
        """
        try:
            with Image.open(image_path) as img:
                file_size = os.path.getsize(image_path)
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2)
                }
        except Exception as e:
            return {'error': str(e)}

def optimize_static_images():
    """
    Fonction utilitaire pour optimiser toutes les images statiques
    """
    static_images_dir = os.path.join(settings.BASE_DIR, 'static', 'images')
    optimized_dir = os.path.join(static_images_dir, 'optimized')
    
    if not os.path.exists(static_images_dir):
        print("Répertoire static/images non trouvé")
        return
    
    # Créer le répertoire optimized
    os.makedirs(optimized_dir, exist_ok=True)
    
    # Traiter chaque image
    for filename in os.listdir(static_images_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(static_images_dir, filename)
            
            # Afficher les infos de l'image originale
            info = ImageOptimizer.get_image_info(image_path)
            print(f"\n📸 {filename}:")
            print(f"   Taille originale: {info.get('size_mb', 0)} MB ({info.get('width', 0)}x{info.get('height', 0)})")
            
            # Créer les versions optimisées
            versions = ImageOptimizer.create_responsive_versions(image_path, optimized_dir)
            
            # Afficher les résultats
            for size_type, optimized_path in versions.items():
                if os.path.exists(optimized_path):
                    opt_info = ImageOptimizer.get_image_info(optimized_path)
                    reduction = round((1 - opt_info.get('size_mb', 0) / info.get('size_mb', 1)) * 100, 1)
                    print(f"   ✅ {size_type}: {opt_info.get('size_mb', 0)} MB (-{reduction}%)")

if __name__ == "__main__":
    optimize_static_images()
