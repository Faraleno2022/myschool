"""
Script simple pour optimiser les images sans commande Django
Usage: python optimize_images_simple.py
"""
import os
from PIL import Image

def optimize_image(image_path, output_dir, quality=80):
    """Optimise une image en réduisant sa taille"""
    try:
        with Image.open(image_path) as img:
            # Convertir en RGB si nécessaire
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                img = background
            
            # Redimensionner si trop grande
            max_size = (1200, 1200)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Créer le nom de fichier optimisé
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_optimized.jpg")
            
            # Sauvegarder avec compression
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            
            # Calculer la réduction de taille
            original_size = os.path.getsize(image_path)
            optimized_size = os.path.getsize(output_path)
            reduction = round((1 - optimized_size / original_size) * 100, 1)
            
            print(f"✅ {os.path.basename(image_path)}")
            print(f"   Original: {round(original_size/(1024*1024), 2)} MB")
            print(f"   Optimisé: {round(optimized_size/(1024*1024), 2)} MB")
            print(f"   Réduction: {reduction}%\n")
            
            return output_path
            
    except Exception as e:
        print(f"❌ Erreur avec {image_path}: {e}")
        return None

def main():
    print("🚀 Optimisation des images de l'application\n")
    
    # Répertoires à traiter
    base_dir = os.path.dirname(os.path.abspath(__file__))
    static_images_dir = os.path.join(base_dir, 'static', 'images')
    
    if not os.path.exists(static_images_dir):
        print("❌ Répertoire static/images non trouvé")
        return
    
    # Créer le répertoire de sortie
    output_dir = os.path.join(static_images_dir, 'optimized')
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 Traitement du répertoire: {static_images_dir}")
    print(f"📤 Sortie dans: {output_dir}\n")
    
    # Traiter chaque image
    processed = 0
    total_original = 0
    total_optimized = 0
    
    for filename in os.listdir(static_images_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(static_images_dir, filename)
            
            # Calculer la taille originale
            original_size = os.path.getsize(image_path)
            total_original += original_size
            
            # Optimiser l'image
            optimized_path = optimize_image(image_path, output_dir, quality=75)
            
            if optimized_path:
                optimized_size = os.path.getsize(optimized_path)
                total_optimized += optimized_size
                processed += 1
    
    # Résumé
    if processed > 0:
        total_reduction = round((1 - total_optimized / total_original) * 100, 1)
        print(f"📊 RÉSUMÉ:")
        print(f"   Images traitées: {processed}")
        print(f"   Taille originale: {round(total_original/(1024*1024), 2)} MB")
        print(f"   Taille optimisée: {round(total_optimized/(1024*1024), 2)} MB")
        print(f"   Réduction totale: {total_reduction}%")
        print(f"\n✅ Optimisation terminée!")
        print(f"📁 Images optimisées disponibles dans: {output_dir}")
    else:
        print("⚠️ Aucune image trouvée à optimiser")

if __name__ == "__main__":
    main()
