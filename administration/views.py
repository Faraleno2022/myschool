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
from eleves.models import Eleve, Responsable, Classe, HistoriqueEleve, Ecole, GrilleTarifaire
from paiements.models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise
from depenses.models import Depense, CategorieDepense, Fournisseur
from salaires.models import Enseignant, AffectationClasse, EtatSalaire, PeriodeSalaire, DetailHeuresClasse
from utilisateurs.models import JournalActivite, Profil

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
        'salaires': EtatSalaire.objects.count(),
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
    
    # Log de debug
    logger.info(f"Reset request received from {request.user.username}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"AJAX header: {request.headers.get('X-Requested-With')}")
    
    # Vérifier que c'est une requête AJAX
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        logger.warning("Reset request rejected: not AJAX")
        return JsonResponse({
            'success': False,
            'error': 'Cette action nécessite une requête AJAX.'
        })
    
    # Vérifications de sécurité
    confirmation_text = request.POST.get('confirmation_text', '').strip()
    admin_password = request.POST.get('admin_password', '')
    
    logger.info(f"Confirmation text received: '{confirmation_text}'")
    logger.info(f"Password provided: {'Yes' if admin_password else 'No'}")
    
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
            
            suppressions_effectuees = []
            
            try:
                # 1. Supprimer les journaux d'activité
                count = JournalActivite.objects.count()
                JournalActivite.objects.all().delete()
                suppressions_effectuees.append(f"Journaux d'activité: {count}")
                
                # 2. Supprimer les données de paiements
                count = PaiementRemise.objects.count()
                PaiementRemise.objects.all().delete()
                suppressions_effectuees.append(f"Remises paiements: {count}")
                
                count = Paiement.objects.count()
                Paiement.objects.all().delete()
                suppressions_effectuees.append(f"Paiements: {count}")
                
                count = EcheancierPaiement.objects.count()
                EcheancierPaiement.objects.all().delete()
                suppressions_effectuees.append(f"Échéanciers: {count}")
                
                count = RemiseReduction.objects.count()
                RemiseReduction.objects.all().delete()
                suppressions_effectuees.append(f"Remises: {count}")
                
                # 3. Supprimer les données de salaires
                count = DetailHeuresClasse.objects.count()
                DetailHeuresClasse.objects.all().delete()
                suppressions_effectuees.append(f"Détails heures: {count}")
                
                count = EtatSalaire.objects.count()
                EtatSalaire.objects.all().delete()
                suppressions_effectuees.append(f"États salaires: {count}")
                
                count = PeriodeSalaire.objects.count()
                PeriodeSalaire.objects.all().delete()
                suppressions_effectuees.append(f"Périodes salaires: {count}")
                
                count = AffectationClasse.objects.count()
                AffectationClasse.objects.all().delete()
                suppressions_effectuees.append(f"Affectations: {count}")
                
                count = Enseignant.objects.count()
                Enseignant.objects.all().delete()
                suppressions_effectuees.append(f"Enseignants: {count}")
                
                # 4. Supprimer les données de dépenses
                count = Depense.objects.count()
                Depense.objects.all().delete()
                suppressions_effectuees.append(f"Dépenses: {count}")
                
                count = Fournisseur.objects.count()
                Fournisseur.objects.all().delete()
                suppressions_effectuees.append(f"Fournisseurs: {count}")
                
                count = CategorieDepense.objects.count()
                CategorieDepense.objects.all().delete()
                suppressions_effectuees.append(f"Catégories dépenses: {count}")
                
                # 5. Supprimer les données d'élèves
                count = HistoriqueEleve.objects.count()
                HistoriqueEleve.objects.all().delete()
                suppressions_effectuees.append(f"Historiques élèves: {count}")
                
                count = Eleve.objects.count()
                Eleve.objects.all().delete()
                suppressions_effectuees.append(f"Élèves: {count}")
                
                count = Responsable.objects.count()
                Responsable.objects.all().delete()
                suppressions_effectuees.append(f"Responsables: {count}")
                
                # 6. Supprimer les utilisateurs non-admin et leurs profils AVANT les écoles
                # D'abord supprimer les profils des utilisateurs non-admin (ils référencent les écoles)
                count = Profil.objects.filter(user__is_superuser=False).count()
                Profil.objects.filter(user__is_superuser=False).delete()
                suppressions_effectuees.append(f"Profils utilisateurs: {count}")
                
                # Ensuite supprimer les utilisateurs non-admin
                count = User.objects.filter(is_superuser=False).count()
                User.objects.filter(is_superuser=False).delete()
                suppressions_effectuees.append(f"Utilisateurs non-admin: {count}")
                
                # 7. Supprimer les données d'écoles (après les profils qui les référencent)
                count = Classe.objects.count()
                Classe.objects.all().delete()
                suppressions_effectuees.append(f"Classes: {count}")
                
                count = GrilleTarifaire.objects.count()
                GrilleTarifaire.objects.all().delete()
                suppressions_effectuees.append(f"Grilles tarifaires: {count}")
                
                count = Ecole.objects.count()
                Ecole.objects.all().delete()
                suppressions_effectuees.append(f"Écoles: {count}")
                
            except Exception as e:
                logger.error(f"Erreur lors de la suppression: {str(e)}")
                logger.info(f"Suppressions effectuées avant erreur: {suppressions_effectuees}")
                raise e
            
            # 8. Réinitialiser les types et modes de paiement (optionnel)
            # TypePaiement.objects.all().delete()
            # ModePaiement.objects.all().delete()
            
            # Log final
            logger.critical(f"RÉINITIALISATION SYSTÈME terminée. Données supprimées: {stats_avant}")
            logger.info(f"Détail des suppressions: {suppressions_effectuees}")
            
            return JsonResponse({
                'success': True,
                'message': 'Système réinitialisé avec succès. Toutes les données ont été supprimées.',
                'stats_supprimees': stats_avant,
                'detail_suppressions': suppressions_effectuees
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
