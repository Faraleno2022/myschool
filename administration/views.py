from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime
import logging

# Imports des modèles à réinitialiser
from eleves.models import Eleve, Responsable, Classe, HistoriqueEleve
from paiements.models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise
from depenses.models import Depense, CategorieDepense, Fournisseur
from salaires.models import Enseignant, AffectationClasse, Salaire
from utilisateurs.models import JournalActivite, Profil
from ecoles.models import Ecole, GrilleTarifaire

logger = logging.getLogger(__name__)

def is_super_admin(user):
    """Vérifie si l'utilisateur est un super administrateur"""
    return user.is_superuser and user.is_staff

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
def system_reset_dashboard(request):
    """Tableau de bord de réinitialisation du système"""
    
    # Compter les données actuelles
    stats = {
        'eleves': Eleve.objects.count(),
        'responsables': Responsable.objects.count(),
        'classes': Classe.objects.count(),
        'paiements': Paiement.objects.count(),
        'echeanciers': EcheancierPaiement.objects.count(),
        'depenses': Depense.objects.count(),
        'enseignants': Enseignant.objects.count(),
        'salaires': Salaire.objects.count(),
        'journal_activites': JournalActivite.objects.count(),
        'ecoles': Ecole.objects.count(),
        'grilles_tarifaires': GrilleTarifaire.objects.count(),
        'users_non_admin': User.objects.filter(is_superuser=False).count(),
    }
    
    context = {
        'stats': stats,
        'titre_page': 'Réinitialisation Système',
        'warning_message': 'ATTENTION: Cette opération supprimera DÉFINITIVEMENT toutes les données du système!'
    }
    
    return render(request, 'administration/system_reset.html', context)

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
@require_POST
@csrf_protect
def confirm_system_reset(request):
    """Confirmation et exécution de la réinitialisation système"""
    
    # Vérifications de sécurité
    confirmation_text = request.POST.get('confirmation_text', '').strip()
    admin_password = request.POST.get('admin_password', '')
    
    if confirmation_text != 'SUPPRIMER TOUTES LES DONNÉES':
        return JsonResponse({
            'success': False,
            'error': 'Texte de confirmation incorrect. Vous devez taper exactement: SUPPRIMER TOUTES LES DONNÉES'
        })
    
    # Vérifier le mot de passe admin
    if not request.user.check_password(admin_password):
        return JsonResponse({
            'success': False,
            'error': 'Mot de passe administrateur incorrect.'
        })
    
    try:
        with transaction.atomic():
            # Log de l'opération AVANT suppression
            logger.critical(f"RÉINITIALISATION SYSTÈME initiée par {request.user.username} à {timezone.now()}")
            
            # Compter les données avant suppression pour le log
            stats_avant = {
                'eleves': Eleve.objects.count(),
                'paiements': Paiement.objects.count(),
                'depenses': Depense.objects.count(),
                'users': User.objects.filter(is_superuser=False).count(),
            }
            
            # ORDRE DE SUPPRESSION (important pour les contraintes FK)
            
            # 1. Supprimer les journaux d'activité
            JournalActivite.objects.all().delete()
            
            # 2. Supprimer les données de paiements
            PaiementRemise.objects.all().delete()
            Paiement.objects.all().delete()
            EcheancierPaiement.objects.all().delete()
            RemiseReduction.objects.all().delete()
            
            # 3. Supprimer les données de salaires
            Salaire.objects.all().delete()
            AffectationClasse.objects.all().delete()
            Enseignant.objects.all().delete()
            
            # 4. Supprimer les données de dépenses
            Depense.objects.all().delete()
            Fournisseur.objects.all().delete()
            CategorieDepense.objects.all().delete()
            
            # 5. Supprimer les données d'élèves
            HistoriqueEleve.objects.all().delete()
            Eleve.objects.all().delete()
            Responsable.objects.all().delete()
            
            # 6. Supprimer les données d'écoles
            Classe.objects.all().delete()
            GrilleTarifaire.objects.all().delete()
            Ecole.objects.all().delete()
            
            # 7. Supprimer les utilisateurs non-admin
            User.objects.filter(is_superuser=False).delete()
            Profil.objects.filter(user__is_superuser=False).delete()
            
            # 8. Réinitialiser les types et modes de paiement (optionnel)
            # TypePaiement.objects.all().delete()
            # ModePaiement.objects.all().delete()
            
            # Log final
            logger.critical(f"RÉINITIALISATION SYSTÈME terminée. Données supprimées: {stats_avant}")
            
            return JsonResponse({
                'success': True,
                'message': 'Système réinitialisé avec succès. Toutes les données ont été supprimées.',
                'stats_supprimees': stats_avant
            })
            
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation système: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la réinitialisation: {str(e)}'
        })

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
def backup_before_reset(request):
    """Créer une sauvegarde avant réinitialisation (optionnel)"""
    
    try:
        # Ici on pourrait implémenter une sauvegarde automatique
        # Pour l'instant, on retourne juste les statistiques
        
        stats = {
            'timestamp': timezone.now().isoformat(),
            'eleves': Eleve.objects.count(),
            'paiements': Paiement.objects.count(),
            'depenses': Depense.objects.count(),
            'users': User.objects.count(),
        }
        
        return JsonResponse({
            'success': True,
            'message': 'Statistiques récupérées pour sauvegarde',
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la préparation de sauvegarde: {str(e)}'
        })
