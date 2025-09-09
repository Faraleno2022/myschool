"""
Middleware pour la gestion multi-tenant des écoles
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from eleves.models import Ecole
from utilisateurs.models import Profil


class EcoleSelectionMiddleware(MiddlewareMixin):
    """
    Middleware pour gérer la sélection d'école dans un système multi-tenant
    """
    
    def process_request(self, request):
        # URLs exemptées du middleware
        exempt_urls = [
            '/static/', '/media/', '/admin/login/', '/admin/logout/',
            '/favicon.ico', '/', '/utilisateurs/login/', '/utilisateurs/logout/',
            '/ecole/inscription/', '/ecole/merci/', '/ecole/creer-etablissement/',
            '/ecole/verifier-statut/'
        ]
        
        # Vérifier si l'URL est exemptée
        if any(request.path.startswith(url) for url in exempt_urls):
            return None
        
        # Si l'utilisateur n'est pas connecté, laisser Django gérer l'authentification
        if not request.user.is_authenticated:
            return None
        
        # Récupérer le profil utilisateur
        try:
            profil = request.user.profil
        except Profil.DoesNotExist:
            # Si pas de profil, rediriger vers la création de profil
            messages.error(request, "Votre profil n'est pas configuré. Contactez l'administrateur.")
            return redirect('utilisateurs:login')
        
        # Si l'utilisateur est un super-utilisateur, permettre l'accès à toutes les écoles
        if request.user.is_superuser:
            # Gérer la sélection d'école pour les super-utilisateurs
            ecole_id = request.session.get('ecole_selectionnee')
            if ecole_id:
                try:
                    ecole = Ecole.objects.get(id=ecole_id, statut='ACTIVE')
                    request.ecole_courante = ecole
                except Ecole.DoesNotExist:
                    request.session.pop('ecole_selectionnee', None)
                    request.ecole_courante = None
            else:
                request.ecole_courante = None
            return None
        
        # Pour les autres utilisateurs, utiliser leur école assignée
        if profil.ecole:
            request.ecole_courante = profil.ecole
            # Stocker l'école dans la session pour cohérence
            request.session['ecole_selectionnee'] = profil.ecole.id
            return None
        else:
            # L'utilisateur n'a pas d'école assignée - rediriger vers création d'établissement
            return redirect('inscription_ecoles:creer_etablissement')
        
        return None


class EcoleContextMiddleware(MiddlewareMixin):
    """
    Middleware pour ajouter le contexte de l'école courante aux templates
    """
    
    def process_template_response(self, request, response):
        if hasattr(response, 'context_data') and response.context_data is not None:
            # Ajouter l'école courante au contexte
            if hasattr(request, 'ecole_courante'):
                response.context_data['ecole_courante'] = request.ecole_courante
            
            # Ajouter la liste des écoles pour les super admins
            if request.user.is_authenticated and request.user.is_superuser:
                response.context_data['ecoles_disponibles'] = Ecole.objects.filter(
                    statut='ACTIVE'
                ).order_by('nom')
        
        return response


class PermissionEcoleMiddleware(MiddlewareMixin):
    """
    Middleware pour vérifier les permissions spécifiques à l'école
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Si l'utilisateur n'est pas connecté, laisser Django gérer
        if not request.user.is_authenticated:
            return None
        
        # Si super admin, autoriser tout
        if request.user.is_superuser:
            return None
        
        # Vérifier si l'utilisateur a accès à l'école courante
        if hasattr(request, 'ecole_courante') and request.ecole_courante:
            try:
                profil = request.user.profil
                if profil.ecole != request.ecole_courante:
                    messages.error(request, "Vous n'avez pas accès à cette école.")
                    return redirect('home')
            except Profil.DoesNotExist:
                return redirect('utilisateurs:login')
        
        return None
