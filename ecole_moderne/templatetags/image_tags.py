"""
Template tags pour l'optimisation des images
"""
from django import template
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.core.cache import caches
import os
from django.conf import settings

register = template.Library()

@register.simple_tag
def optimized_image(image_path, size='medium', alt='', css_class='', loading='lazy'):
    """
    Template tag pour afficher une image optimisée avec lazy loading
    
    Usage:
    {% optimized_image 'images/ecole.jpg' size='large' alt='École' css_class='hero-image' %}
    """
    # Cache pour éviter de recalculer les chemins
    image_cache = caches['images']
    cache_key = f"optimized_image_{image_path}_{size}"
    
    cached_result = image_cache.get(cache_key)
    if cached_result:
        return mark_safe(cached_result)
    
    # Construire le chemin vers l'image optimisée
    base_name = os.path.splitext(image_path)[0]
    optimized_path = f"{base_name}_optimized/{os.path.basename(base_name)}_{size}.webp"
    
    # Vérifier si l'image optimisée existe
    full_optimized_path = os.path.join(settings.BASE_DIR, 'static', optimized_path)
    
    if os.path.exists(full_optimized_path):
        # Utiliser l'image optimisée
        src = static(optimized_path)
        fallback_src = static(image_path)
    else:
        # Utiliser l'image originale si pas d'optimisée
        src = static(image_path)
        fallback_src = src
    
    # Construire le HTML avec support WebP et fallback
    html = f'''
    <picture>
        <source srcset="{src}" type="image/webp">
        <img src="{fallback_src}" 
             alt="{alt}" 
             class="{css_class}"
             loading="{loading}"
             decoding="async"
             onerror="this.onerror=null;this.src='{fallback_src}';">
    </picture>
    '''
    
    # Mettre en cache le résultat
    image_cache.set(cache_key, html, 3600)  # Cache 1 heure
    
    return mark_safe(html)

@register.simple_tag
def responsive_image(image_path, alt='', css_class='', loading='lazy'):
    """
    Template tag pour une image responsive avec plusieurs tailles
    
    Usage:
    {% responsive_image 'images/carte1.jpg' alt='Carte 1' css_class='card-img-top' %}
    """
    base_name = os.path.splitext(image_path)[0]
    
    # Construire les sources pour différentes tailles
    sources = []
    sizes = ['small', 'medium', 'large']
    
    for size in sizes:
        optimized_path = f"{base_name}_optimized/{os.path.basename(base_name)}_{size}.webp"
        full_path = os.path.join(settings.BASE_DIR, 'static', optimized_path)
        
        if os.path.exists(full_path):
            src = static(optimized_path)
            
            # Définir les media queries selon la taille
            if size == 'small':
                media = '(max-width: 576px)'
            elif size == 'medium':
                media = '(max-width: 992px)'
            else:
                media = '(min-width: 993px)'
            
            sources.append(f'<source media="{media}" srcset="{src}" type="image/webp">')
    
    # Image de fallback
    fallback_src = static(image_path)
    
    html = f'''
    <picture>
        {''.join(sources)}
        <img src="{fallback_src}" 
             alt="{alt}" 
             class="{css_class}"
             loading="{loading}"
             decoding="async">
    </picture>
    '''
    
    return mark_safe(html)

@register.simple_tag
def eleve_photo(eleve, size='small', css_class=''):
    """
    Template tag spécialisé pour les photos d'élèves avec fallback
    
    Usage:
    {% eleve_photo eleve size='thumbnail' css_class='profile-photo' %}
    """
    if eleve.photo:
        # Construire le chemin optimisé
        photo_name = os.path.splitext(os.path.basename(eleve.photo.name))[0]
        optimized_path = f"eleves/photos/optimized/{photo_name}_{size}.webp"
        full_path = os.path.join(settings.BASE_DIR, optimized_path)
        
        if os.path.exists(full_path):
            # Utiliser la version optimisée
            src = f"/media/{optimized_path}"
        else:
            # Utiliser l'originale
            src = eleve.photo.url
        
        html = f'''
        <img src="{src}" 
             alt="Photo de {eleve.nom_complet}" 
             class="{css_class}"
             loading="lazy"
             decoding="async"
             onerror="this.onerror=null;this.src='{eleve.photo.url}';">
        '''
    else:
        # Placeholder si pas de photo
        html = f'''
        <div class="{css_class} d-flex align-items-center justify-content-center bg-secondary text-white">
            <i class="fas fa-user"></i>
        </div>
        '''
    
    return mark_safe(html)

@register.filter
def file_size(value):
    """
    Filtre pour afficher la taille d'un fichier de manière lisible
    
    Usage:
    {{ image.size|file_size }}
    """
    try:
        size = float(value)
        
        if size < 1024:
            return f"{size:.0f} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size/(1024*1024):.1f} MB"
        else:
            return f"{size/(1024*1024*1024):.1f} GB"
    except (ValueError, TypeError):
        return "0 B"
