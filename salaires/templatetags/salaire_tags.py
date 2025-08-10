from django import template
from django.db.models import Count, Q

register = template.Library()

@register.filter
def etats_valides(periode):
    """Retourne le nombre d'états de salaire validés pour une période"""
    return periode.etats_salaire.filter(valide=True).count()

@register.filter
def etats_payes(periode):
    """Retourne le nombre d'états de salaire payés pour une période"""
    return periode.etats_salaire.filter(paye=True).count()

@register.filter
def etats_en_attente(periode):
    """Retourne le nombre d'états de salaire en attente pour une période"""
    return periode.etats_salaire.filter(valide=False, paye=False).count()

@register.simple_tag
def stats_periode(periode):
    """Retourne les statistiques complètes d'une période"""
    etats = periode.etats_salaire.all()
    return {
        'total': etats.count(),
        'valides': etats.filter(valide=True).count(),
        'payes': etats.filter(paye=True).count(),
        'en_attente': etats.filter(valide=False, paye=False).count(),
    }
