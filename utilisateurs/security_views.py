"""
Vues sécurisées pour l'authentification avec protection contre les attaques
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.db import OperationalError, transaction, connection
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Obtient l'adresse IP réelle du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_ip_blocked(ip, username=None):
    """Vérifie si une IP ou un couple IP+username est bloqué."""
    # Blocage global IP
    if cache.get(f"blocked_login_{ip}", False):
        return True
    # Blocage ciblé IP+username
    if username:
        return cache.get(f"blocked_login_{ip}_{username.lower()}", False)
    return False

def block_ip(ip, duration=300):
    """Bloque une IP pour une durée donnée (helper rétro-compatible)."""
    cache_key = f"blocked_login_{ip}"
    cache.set(cache_key, True, duration)
    logger.warning(f"IP {ip} bloquée pour tentatives de connexion répétées")

def block_ip_username(ip, username, duration=900):
    """Bloque un couple IP+username pour une durée donnée (par défaut 15 min)."""
    if not username:
        return block_ip(ip, duration)
    cache_key = f"blocked_login_{ip}_{username.lower()}"
    cache.set(cache_key, True, duration)
    logger.warning(f"Blocage IP+username activé: {ip} / {username}")

def get_failed_attempts(ip, username=None):
    """Obtient le nombre de tentatives échouées pour une IP ou IP+username."""
    if username:
        key = f"failed_login_{ip}_{username.lower()}"
    else:
        key = f"failed_login_{ip}"
    return cache.get(key, 0)

def increment_failed_attempts(ip, username=None, ttl=900):
    """Incrémente le compteur de tentatives échouées (IP+username si fourni)."""
    if username:
        cache_key = f"failed_login_{ip}_{username.lower()}"
    else:
        cache_key = f"failed_login_{ip}"
    attempts = cache.get(cache_key, 0) + 1
    cache.set(cache_key, attempts, ttl)  # 15 minutes
    return attempts

def reset_failed_attempts(ip, username=None):
    """Remet à zéro le compteur de tentatives échouées (IP+username si fourni)."""
    if username:
        cache.delete(f"failed_login_{ip}_{username.lower()}")
    cache.delete(f"failed_login_{ip}")

@ensure_csrf_cookie
@csrf_protect
@never_cache
def secure_login(request):
    """
    Vue de connexion sécurisée avec protection contre la force brute
    """
    client_ip = get_client_ip(request)
    
    # Vérifier si l'IP est bloquée (pré-POST)
    if is_ip_blocked(client_ip):
        logger.warning(f"Tentative de connexion depuis IP bloquée: {client_ip}")
        return render(request, 'utilisateurs/login.html', {
            'error': 'Votre adresse IP a été temporairement bloquée. Veuillez réessayer plus tard.',
            'blocked': True
        })
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        # Validation basique
        if not username or not password:
            messages.error(request, 'Nom d\'utilisateur et mot de passe requis.')
            return render(request, 'utilisateurs/login.html')
        
        # Limiter la longueur des champs pour éviter les attaques DoS
        if len(username) > 150 or len(password) > 128:
            logger.warning(f"Tentative de connexion avec champs trop longs depuis IP: {client_ip}")
            messages.error(request, 'Données invalides.')
            return render(request, 'utilisateurs/login.html')
        
        # Vérifier un éventuel blocage ciblé IP+username
        if is_ip_blocked(client_ip, username=username):
            logger.warning(f"Tentative de connexion depuis IP+username bloqués: {client_ip} / {username}")
            return render(request, 'utilisateurs/login.html', {
                'error': 'Trop de tentatives. Veuillez réessayer plus tard.',
                'blocked': True
            })

        # Authentification
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                # Connexion réussie
                login(request, user)
                reset_failed_attempts(client_ip, username=username)
                
                # Log de connexion réussie
                logger.info(f"Connexion réussie: {username} depuis IP: {client_ip}")
                
                # Redirection sécurisée
                next_url = request.GET.get('next')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect('eleves:liste_eleves')
            else:
                messages.error(request, 'Compte désactivé.')
                logger.warning(f"Tentative de connexion sur compte désactivé: {username} depuis IP: {client_ip}")
        else:
            # Échec de connexion
            attempts = increment_failed_attempts(client_ip, username=username, ttl=900)

            logger.warning(f"Échec de connexion: {username} depuis IP: {client_ip} (tentative {attempts})")

            # Bloquer après 5 tentatives (15 minutes)
            if attempts >= 5:
                block_ip_username(client_ip, username, duration=900)
                messages.error(request, 'Trop de tentatives échouées. Accès temporairement bloqué.')
            else:
                # Message discret sans indiquer le nombre restant
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    
    return render(request, 'utilisateurs/login.html')

@login_required
def secure_logout(request):
    """
    Déconnexion sécurisée avec nettoyage de session
    """
    username = request.user.username
    client_ip = get_client_ip(request)
    
    # Log de déconnexion
    logger.info(f"Déconnexion: {username} depuis IP: {client_ip}")
    
    # Déconnexion et nettoyage de session
    logout(request)
    request.session.flush()
    
    messages.success(request, 'Vous avez été déconnecté avec succès.')
    return redirect('utilisateurs:login')

@method_decorator([csrf_protect, never_cache], name='dispatch')
class SecurePasswordChangeView(View):
    """
    Vue sécurisée pour changer le mot de passe
    """
    
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('utilisateurs:login')
        
        return render(request, 'utilisateurs/change_password.html')
    
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('utilisateurs:login')
        
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validation
        if not all([current_password, new_password, confirm_password]):
            messages.error(request, 'Tous les champs sont requis.')
            return render(request, 'utilisateurs/change_password.html')
        
        if new_password != confirm_password:
            messages.error(request, 'Les nouveaux mots de passe ne correspondent pas.')
            return render(request, 'utilisateurs/change_password.html')
        
        if len(new_password) < 12:
            messages.error(request, 'Le mot de passe doit contenir au moins 12 caractères.')
            return render(request, 'utilisateurs/change_password.html')
        
        # Vérifier le mot de passe actuel
        if not request.user.check_password(current_password):
            client_ip = get_client_ip(request)
            logger.warning(f"Tentative de changement de mot de passe avec mauvais mot de passe actuel: {request.user.username} depuis IP: {client_ip}")
            messages.error(request, 'Mot de passe actuel incorrect.')
            return render(request, 'utilisateurs/change_password.html')
        
        # Changer le mot de passe avec retries pour éviter les verrous SQLite
        last_error = None
        for attempt in range(3):
            try:
                with transaction.atomic():
                    request.user.set_password(new_password)
                    request.user.save()
                last_error = None
                break
            except OperationalError as e:
                last_error = e
                # Retente uniquement si c'est un verrou SQLite
                if 'locked' in str(e).lower() or 'database is locked' in str(e).lower():
                    # Fermer la connexion et attendre un peu avant de retenter
                    try:
                        connection.close()
                    except Exception:
                        pass
                    time.sleep(1 + attempt)
                    continue
                else:
                    break
        if last_error:
            logger.error(f"Erreur lors de l'enregistrement du nouveau mot de passe pour {request.user.username}: {last_error}")
            messages.error(request, "Impossible d'enregistrer le nouveau mot de passe pour le moment. Veuillez réessayer.")
            return render(request, 'utilisateurs/change_password.html')
        
        # Log du changement
        client_ip = get_client_ip(request)
        logger.info(f"Changement de mot de passe réussi: {request.user.username} depuis IP: {client_ip}")
        
        messages.success(request, 'Mot de passe changé avec succès. Veuillez vous reconnecter.')
        
        # Déconnecter l'utilisateur pour qu'il se reconnecte
        logout(request)
        return redirect('utilisateurs:login')

def security_dashboard(request):
    """
    Tableau de bord de sécurité pour les administrateurs
    """
    if not request.user.is_staff:
        return HttpResponseForbidden("Accès réservé aux administrateurs.")
    
    # Statistiques de sécurité
    stats = {
        'blocked_ips': len([key for key in cache._cache.keys() if key.startswith('blocked_')]),
        'failed_attempts': len([key for key in cache._cache.keys() if key.startswith('failed_login_')]),
        'active_sessions': len([key for key in cache._cache.keys() if key.startswith('session_')]),
    }
    
    return render(request, 'administration/security_dashboard.html', {
        'stats': stats
    })

def check_session_security(request):
    """
    Vérifie la sécurité de la session actuelle
    """
    if not request.user.is_authenticated:
        return redirect('utilisateurs:login')
    
    # Vérifier l'âge de la session
    session_start = request.session.get('session_start')
    if not session_start:
        request.session['session_start'] = time.time()
        session_start = request.session['session_start']
    
    session_age = time.time() - session_start
    
    # Forcer la reconnexion après 8 heures
    if session_age > 28800:  # 8 heures
        logger.info(f"Session expirée pour {request.user.username} (durée: {session_age/3600:.1f}h)")
        logout(request)
        messages.info(request, 'Votre session a expiré. Veuillez vous reconnecter.')
        return redirect('utilisateurs:login')
    
    return None  # Session valide
