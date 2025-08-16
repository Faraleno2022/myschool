from django import template

register = template.Library()

@register.filter
def getattr(obj, attr):
    """Filtre personnalisé pour accéder aux attributs d'un objet"""
    try:
        import builtins
        return builtins.getattr(obj, attr)
    except (AttributeError, TypeError):
        return None

@register.filter
def get_item(dictionary, key):
    """Filtre pour accéder aux éléments d'un dictionnaire"""
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None

@register.filter
def verbose_name(obj):
    """Retourne le nom verbose du modèle"""
    try:
        return obj._meta.verbose_name
    except AttributeError:
        return str(obj.__class__.__name__)

@register.filter
def model_name(obj):
    """Retourne le nom du modèle"""
    try:
        return obj._meta.model_name
    except AttributeError:
        return str(obj.__class__.__name__).lower()

@register.filter
def app_label(obj):
    """Retourne le label de l'application"""
    try:
        return obj._meta.app_label
    except AttributeError:
        return 'unknown'
