"""
Décorateurs pour la gestion des permissions multi-tenant
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Profil


def ecole_required(view_func):
    """
    Décorateur qui s'assure qu'une école est sélectionnée
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request, 'ecole_courante') or not request.ecole_courante:
            messages.error(request, "Aucune école sélectionnée.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def role_required(*roles):
    """
    Décorateur qui vérifie si l'utilisateur a un des rôles requis
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            try:
                profil = request.user.profil
                if profil.role not in roles and not request.user.is_superuser:
                    raise PermissionDenied("Vous n'avez pas les permissions nécessaires.")
                return view_func(request, *args, **kwargs)
            except Profil.DoesNotExist:
                messages.error(request, "Profil utilisateur non configuré.")
                return redirect('utilisateurs:login')
        return _wrapped_view
    return decorator


def permission_required(permission_name):
    """
    Décorateur qui vérifie une permission spécifique du profil
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            try:
                profil = request.user.profil
                if not getattr(profil, permission_name, False):
                    raise PermissionDenied(f"Permission '{permission_name}' requise.")
                return view_func(request, *args, **kwargs)
            except Profil.DoesNotExist:
                messages.error(request, "Profil utilisateur non configuré.")
                return redirect('utilisateurs:login')
        return _wrapped_view
    return decorator


def admin_or_directeur_required(view_func):
    """
    Décorateur pour les vues nécessitant un niveau admin ou directeur
    """
    return role_required('ADMIN', 'DIRECTEUR')(view_func)


def comptable_required(view_func):
    """
    Décorateur pour les vues nécessitant un niveau comptable minimum
    """
    return role_required('ADMIN', 'DIRECTEUR', 'COMPTABLE')(view_func)


def enseignant_required(view_func):
    """
    Décorateur pour les vues accessibles aux enseignants
    """
    return role_required('ADMIN', 'DIRECTEUR', 'ENSEIGNANT')(view_func)


def same_ecole_required(view_func):
    """
    Décorateur qui s'assure que l'utilisateur appartient à la même école
    que l'objet qu'il tente de consulter/modifier
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        try:
            profil = request.user.profil
            if hasattr(request, 'ecole_courante') and request.ecole_courante:
                if profil.ecole != request.ecole_courante:
                    raise PermissionDenied("Accès refusé à cette école.")
            return view_func(request, *args, **kwargs)
        except Profil.DoesNotExist:
            messages.error(request, "Profil utilisateur non configuré.")
            return redirect('utilisateurs:login')
    return _wrapped_view


class PermissionMixin:
    """
    Mixin pour les vues basées sur les classes avec gestion des permissions
    """
    required_role = None
    required_permission = None
    require_same_ecole = True
    
    def dispatch(self, request, *args, **kwargs):
        # Vérifier l'authentification
        if not request.user.is_authenticated:
            return redirect('utilisateurs:login')
        
        # Super admin a tous les droits
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        try:
            profil = request.user.profil
        except Profil.DoesNotExist:
            messages.error(request, "Profil utilisateur non configuré.")
            return redirect('utilisateurs:login')
        
        # Vérifier le rôle requis
        if self.required_role and profil.role != self.required_role:
            raise PermissionDenied(f"Rôle '{self.required_role}' requis.")
        
        # Vérifier la permission spécifique
        if self.required_permission and not getattr(profil, self.required_permission, False):
            raise PermissionDenied(f"Permission '{self.required_permission}' requise.")
        
        # Vérifier l'appartenance à la même école
        if self.require_same_ecole and hasattr(request, 'ecole_courante'):
            if profil.ecole != request.ecole_courante:
                raise PermissionDenied("Accès refusé à cette école.")
        
        return super().dispatch(request, *args, **kwargs)
