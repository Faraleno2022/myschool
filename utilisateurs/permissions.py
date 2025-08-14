"""
Décorateurs et fonctions pour gérer les permissions granulaires des utilisateurs
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)

def has_permission(user, permission_name):
    """
    Vérifie si un utilisateur a une permission spécifique
    """
    if not user.is_authenticated:
        return False
    
    # Les superusers ont toutes les permissions
    if user.is_superuser:
        return True
    
    # Vérifier le profil utilisateur
    profil = getattr(user, 'profil', None)
    if not profil:
        return False
    
    # Les admins ont toutes les permissions
    if profil.role == 'ADMIN':
        return True
    
    # Vérifier la permission spécifique
    return getattr(profil, permission_name, False)

def permission_required(permission_name, message=None):
    """
    Décorateur pour vérifier qu'un utilisateur a une permission spécifique
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, permission_name):
                # Log de la tentative d'accès non autorisée
                logger.warning(
                    f"Accès refusé: {request.user.username} a tenté d'accéder à {view_func.__name__} "
                    f"sans la permission {permission_name}"
                )
                
                # Message personnalisé ou par défaut
                error_message = message or f"Vous n'avez pas la permission requise: {permission_name}"
                
                return render(request, 'utilisateurs/permission_denied.html', {
                    'error_message': error_message,
                    'permission_name': permission_name,
                    'user_role': getattr(request.user.profil, 'role', 'INCONNU') if hasattr(request.user, 'profil') else 'INCONNU'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def can_add_payments(view_func):
    """Décorateur pour vérifier la permission d'ajouter des paiements"""
    return permission_required(
        'peut_ajouter_paiements',
        "Vous n'êtes pas autorisé à ajouter des paiements."
    )(view_func)

def can_add_expenses(view_func):
    """Décorateur pour vérifier la permission d'ajouter des dépenses"""
    return permission_required(
        'peut_ajouter_depenses',
        "Vous n'êtes pas autorisé à ajouter des dépenses."
    )(view_func)

def can_add_teachers(view_func):
    """Décorateur pour vérifier la permission d'ajouter des enseignants"""
    return permission_required(
        'peut_ajouter_enseignants',
        "Vous n'êtes pas autorisé à ajouter des enseignants."
    )(view_func)

def can_modify_payments(view_func):
    """Décorateur pour vérifier la permission de modifier des paiements"""
    return permission_required(
        'peut_modifier_paiements',
        "Vous n'êtes pas autorisé à modifier des paiements."
    )(view_func)

def can_modify_expenses(view_func):
    """Décorateur pour vérifier la permission de modifier des dépenses"""
    return permission_required(
        'peut_modifier_depenses',
        "Vous n'êtes pas autorisé à modifier des dépenses."
    )(view_func)

def can_delete_payments(view_func):
    """Décorateur pour vérifier la permission de supprimer des paiements"""
    return permission_required(
        'peut_supprimer_paiements',
        "Vous n'êtes pas autorisé à supprimer des paiements."
    )(view_func)

def can_delete_expenses(view_func):
    """Décorateur pour vérifier la permission de supprimer des dépenses"""
    return permission_required(
        'peut_supprimer_depenses',
        "Vous n'êtes pas autorisé à supprimer des dépenses."
    )(view_func)

def can_validate_payments(view_func):
    """Décorateur pour vérifier la permission de valider des paiements"""
    return permission_required(
        'peut_valider_paiements',
        "Vous n'êtes pas autorisé à valider des paiements."
    )(view_func)

def can_validate_expenses(view_func):
    """Décorateur pour vérifier la permission de valider des dépenses"""
    return permission_required(
        'peut_valider_depenses',
        "Vous n'êtes pas autorisé à valider des dépenses."
    )(view_func)

def can_generate_reports(view_func):
    """Décorateur pour vérifier la permission de générer des rapports"""
    return permission_required(
        'peut_generer_rapports',
        "Vous n'êtes pas autorisé à générer des rapports."
    )(view_func)

def can_view_reports(view_func):
    """Décorateur pour vérifier la permission de consulter des rapports"""
    return permission_required(
        'peut_consulter_rapports',
        "Vous n'êtes pas autorisé à consulter des rapports."
    )(view_func)

def can_manage_users(view_func):
    """Décorateur pour vérifier la permission de gérer des utilisateurs"""
    return permission_required(
        'peut_gerer_utilisateurs',
        "Vous n'êtes pas autorisé à gérer des utilisateurs."
    )(view_func)

# Fonctions utilitaires pour les templates
def get_user_permissions(user):
    """
    Retourne un dictionnaire des permissions de l'utilisateur
    """
    if not user.is_authenticated:
        return {}
    
    if user.is_superuser:
        return {
            'can_add_payments': True,
            'can_add_expenses': True,
            'can_add_teachers': True,
            'can_modify_payments': True,
            'can_modify_expenses': True,
            'can_delete_payments': True,
            'can_delete_expenses': True,
            'can_validate_payments': True,
            'can_validate_expenses': True,
            'can_generate_reports': True,
            'can_view_reports': True,
            'can_manage_users': True,
        }
    
    profil = getattr(user, 'profil', None)
    if not profil:
        return {}
    
    if profil.role == 'ADMIN':
        return {
            'can_add_payments': True,
            'can_add_expenses': True,
            'can_add_teachers': True,
            'can_modify_payments': True,
            'can_modify_expenses': True,
            'can_delete_payments': True,
            'can_delete_expenses': True,
            'can_validate_payments': True,
            'can_validate_expenses': True,
            'can_generate_reports': True,
            'can_view_reports': True,
            'can_manage_users': True,
        }
    
    return {
        'can_add_payments': profil.peut_ajouter_paiements,
        'can_add_expenses': profil.peut_ajouter_depenses,
        'can_add_teachers': profil.peut_ajouter_enseignants,
        'can_modify_payments': profil.peut_modifier_paiements,
        'can_modify_expenses': profil.peut_modifier_depenses,
        'can_delete_payments': profil.peut_supprimer_paiements,
        'can_delete_expenses': profil.peut_supprimer_depenses,
        'can_validate_payments': profil.peut_valider_paiements,
        'can_validate_expenses': profil.peut_valider_depenses,
        'can_generate_reports': profil.peut_generer_rapports,
        'can_view_reports': profil.peut_consulter_rapports,
        'can_manage_users': profil.peut_gerer_utilisateurs,
    }

def check_comptable_restrictions(user):
    """
    Vérifie les restrictions spécifiques pour les comptables
    Retourne un dictionnaire des restrictions
    """
    if not user.is_authenticated:
        return {'all_restricted': True}
    
    if user.is_superuser:
        return {'all_restricted': False}
    
    profil = getattr(user, 'profil', None)
    if not profil:
        return {'all_restricted': True}
    
    if profil.role in ['ADMIN', 'DIRECTEUR']:
        return {'all_restricted': False}
    
    if profil.role == 'COMPTABLE':
        return {
            'all_restricted': False,
            'cannot_add_payments': not profil.peut_ajouter_paiements,
            'cannot_add_expenses': not profil.peut_ajouter_depenses,
            'cannot_add_teachers': not profil.peut_ajouter_enseignants,
            'cannot_modify_payments': not profil.peut_modifier_paiements,
            'cannot_modify_expenses': not profil.peut_modifier_depenses,
            'cannot_delete_payments': not profil.peut_supprimer_paiements,
            'cannot_delete_expenses': not profil.peut_supprimer_depenses,
        }
    
    return {'all_restricted': True}
