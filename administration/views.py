from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.db.models.deletion import ProtectedError
from django.apps import apps
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, F, Value, Sum, Case, When, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce, Least, Greatest
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
import logging
import json
from ecole_moderne.security_decorators import delete_permission_required
from utilisateurs.utils import filter_by_user_school

# Imports des modèles à réinitialiser
from eleves.models import Eleve, Responsable, Classe, HistoriqueEleve, Ecole, GrilleTarifaire
from paiements.models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise, Relance
from depenses.models import Depense, CategorieDepense, Fournisseur
from salaires.models import Enseignant, AffectationClasse, EtatSalaire, PeriodeSalaire, DetailHeuresClasse
from utilisateurs.models import JournalActivite, Profil

logger = logging.getLogger(__name__)

def is_super_admin(user):
    """Vérifie si l'utilisateur est un super administrateur"""
    return user.is_superuser and user.is_staff

def can_access_retards_paiement(user):
    """Vérifie si l'utilisateur peut accéder aux retards de paiement"""
    if not user.is_authenticated:
        return False
    
    # Super admin et staff ont accès
    if user.is_superuser or user.is_staff:
        return True
    
    # Vérifier le rôle via le profil
    try:
        profil = user.profil
        return profil.role in ['ADMIN', 'COMPTABLE', 'DIRECTEUR']
    except:
        return False

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
    
    # Accès déjà contrôlé par les décorateurs @login_required et @user_passes_test(is_super_admin)
    # Suppression de la restriction hardcodée sur le nom d'utilisateur pour permettre à tout super admin/staff
    # d'exécuter la réinitialisation conformément aux règles de sécurité globales.

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

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
def database_management(request):
    """Interface de gestion des bases de données"""
    
    # Définir les modèles à gérer avec leurs métadonnées
    models_config = {
        'eleves': {
            'models': [
                {'model': Eleve, 'name': 'Élèves', 'icon': 'fas fa-user-graduate'},
                {'model': Responsable, 'name': 'Responsables', 'icon': 'fas fa-users'},
                {'model': Classe, 'name': 'Classes', 'icon': 'fas fa-chalkboard'},
                {'model': Ecole, 'name': 'Écoles', 'icon': 'fas fa-school'},
                {'model': GrilleTarifaire, 'name': 'Grilles Tarifaires', 'icon': 'fas fa-table'},
                {'model': HistoriqueEleve, 'name': 'Historique Élèves', 'icon': 'fas fa-history'},
            ],
            'category': 'Gestion des Élèves',
            'color': 'primary'
        },
        'paiements': {
            'models': [
                {'model': Paiement, 'name': 'Paiements', 'icon': 'fas fa-money-bill'},
                {'model': EcheancierPaiement, 'name': 'Échéanciers', 'icon': 'fas fa-calendar-alt'},
                {'model': TypePaiement, 'name': 'Types de Paiement', 'icon': 'fas fa-tags'},
                {'model': ModePaiement, 'name': 'Modes de Paiement', 'icon': 'fas fa-credit-card'},
                {'model': RemiseReduction, 'name': 'Remises', 'icon': 'fas fa-percent'},
                {'model': PaiementRemise, 'name': 'Paiements-Remises', 'icon': 'fas fa-link'},
            ],
            'category': 'Gestion des Paiements',
            'color': 'success'
        },
        'salaires': {
            'models': [
                {'model': Enseignant, 'name': 'Enseignants', 'icon': 'fas fa-chalkboard-teacher'},
                {'model': AffectationClasse, 'name': 'Affectations Classes', 'icon': 'fas fa-link'},
                {'model': EtatSalaire, 'name': 'États Salaires', 'icon': 'fas fa-money-check'},
                {'model': PeriodeSalaire, 'name': 'Périodes Salaires', 'icon': 'fas fa-calendar'},
                {'model': DetailHeuresClasse, 'name': 'Détails Heures', 'icon': 'fas fa-clock'},
            ],
            'category': 'Gestion des Salaires',
            'color': 'info'
        },
        'depenses': {
            'models': [
                {'model': Depense, 'name': 'Dépenses', 'icon': 'fas fa-receipt'},
                {'model': CategorieDepense, 'name': 'Catégories Dépenses', 'icon': 'fas fa-list'},
                {'model': Fournisseur, 'name': 'Fournisseurs', 'icon': 'fas fa-truck'},
            ],
            'category': 'Gestion des Dépenses',
            'color': 'warning'
        },
        'utilisateurs': {
            'models': [
                {'model': User, 'name': 'Utilisateurs', 'icon': 'fas fa-user'},
                {'model': Profil, 'name': 'Profils', 'icon': 'fas fa-id-card'},
                {'model': JournalActivite, 'name': 'Journal d\'Activité', 'icon': 'fas fa-clipboard-list'},
            ],
            'category': 'Gestion des Utilisateurs',
            'color': 'danger'
        }
    }
    
    # Calculer les statistiques pour chaque modèle
    for category_key, category_data in models_config.items():
        for model_info in category_data['models']:
            model_info['count'] = model_info['model'].objects.count()
            # Ajouter les métadonnées du modèle pour éviter l'erreur _meta
            model_info['app_label'] = model_info['model']._meta.app_label
            model_info['model_name'] = model_info['model']._meta.model_name
    
    context = {
        'models_config': models_config,
        'titre_page': 'Administration des Bases de Données',
    }
    
    return render(request, 'administration/database_management.html', context)

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
def model_list_view(request, app_label, model_name):
    """Vue pour lister les enregistrements d'un modèle"""
    
    try:
        # Récupérer le modèle
        model = apps.get_model(app_label, model_name)
    except LookupError:
        messages.error(request, f"Modèle {app_label}.{model_name} introuvable.")
        return redirect('administration:database_management')
    
    # Recherche
    search_query = request.GET.get('search', '')
    queryset = model.objects.all()
    
    if search_query:
        # Recherche dans tous les champs texte du modèle
        search_fields = []
        for field in model._meta.fields:
            if field.get_internal_type() in ['CharField', 'TextField']:
                search_fields.append(f"{field.name}__icontains")
        
        if search_fields:
            q_objects = Q()
            for field in search_fields:
                q_objects |= Q(**{field: search_query})
            queryset = queryset.filter(q_objects)
    
    # Pagination avec ordre pour éviter l'avertissement UnorderedObjectListWarning
    if not queryset.ordered:
        # Ajouter un ordre par défaut basé sur la clé primaire
        queryset = queryset.order_by('pk')
    
    paginator = Paginator(queryset, 25)  # 25 éléments par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Récupérer les champs du modèle pour l'affichage
    fields = []
    for field in model._meta.fields:
        if not field.name.endswith('_ptr'):  # Exclure les pointeurs d'héritage
            fields.append({
                'name': field.name,
                'verbose_name': field.verbose_name,
                'type': field.get_internal_type()
            })
    
    context = {
        'model': model,
        'model_name': model_name,
        'app_label': app_label,
        'page_obj': page_obj,
        'fields': fields,
        'search_query': search_query,
        'titre_page': f'Liste des {model._meta.verbose_name_plural}',
        'total_count': model.objects.count(),
        'filtered_count': queryset.count() if search_query else None,
        'verbose_name_plural': model._meta.verbose_name_plural,
        'verbose_name': model._meta.verbose_name,
    }
    
    return render(request, 'administration/model_list.html', context)

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
def model_detail_view(request, app_label, model_name, object_id):
    """Vue pour afficher les détails d'un enregistrement"""
    
    try:
        model = apps.get_model(app_label, model_name)
        obj = get_object_or_404(model, pk=object_id)
    except LookupError:
        messages.error(request, f"Modèle {app_label}.{model_name} introuvable.")
        return redirect('administration:database_management')
    
    # Récupérer tous les champs et leurs valeurs
    field_values = []
    for field in model._meta.fields:
        if not field.name.endswith('_ptr'):
            value = getattr(obj, field.name)
            field_values.append({
                'name': field.name,
                'verbose_name': field.verbose_name,
                'value': value,
                'type': field.get_internal_type()
            })
    
    context = {
        'model': model,
        'object': obj,
        'field_values': field_values,
        'model_name': model_name,
        'app_label': app_label,
        'titre_page': f'Détail {model._meta.verbose_name}',
        'verbose_name': model._meta.verbose_name,
        'verbose_name_plural': model._meta.verbose_name_plural,
        'db_table': model._meta.db_table,
    }
    
    return render(request, 'administration/model_detail.html', context)

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
@csrf_protect
def model_delete_view(request, app_label, model_name, object_id):
    """Vue pour supprimer un enregistrement"""
    
    try:
        model = apps.get_model(app_label, model_name)
        obj = get_object_or_404(model, pk=object_id)
    except LookupError:
        return JsonResponse({
            'success': False,
            'error': f"Modèle {app_label}.{model_name} introuvable."
        })
    
    # Vérifier que c'est une requête AJAX
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'error': 'Cette action nécessite une requête AJAX.'
        })
    
    try:
        obj_str = str(obj)
        obj.delete()
        
        # Log de l'action
        logger.info(f"Suppression {model._meta.verbose_name}: {obj_str} par {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'{model._meta.verbose_name} "{obj_str}" supprimé avec succès.'
        })
        
    except ProtectedError as e:
        # Construire un message clair avec les relations bloquantes
        blocking = []
        try:
            # e.protected_objects peut contenir les objets liés qui bloquent
            related = getattr(e, 'protected_objects', [])
            if related:
                # Compter par modèle pour un message synthétique
                counts = {}
                for ro in related:
                    key = ro._meta.verbose_name_plural
                    counts[key] = counts.get(key, 0) + 1
                for label, cnt in counts.items():
                    blocking.append(f"{cnt} {label}")
        except Exception:
            pass
        details = f" — dépendances: {', '.join(blocking)}" if blocking else ''
        logger.warning(f"Suppression bloquée (ProtectedError) {model._meta.verbose_name} {object_id}{details}")
        return JsonResponse({
            'success': False,
            'error': (
                "Suppression impossible: cet élément est référencé par d'autres données protégées"
                + details
                + ". Supprimez/retirez d'abord ces éléments liés."
            )
        })
    except IntegrityError as e:
        logger.error(f"IntegrityError lors de la suppression {model._meta.verbose_name} {object_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': "Suppression impossible à cause d'une contrainte d'intégrité (FK/UNIQUE)."
        })
    except Exception as e:
        logger.error(f"Erreur lors de la suppression {model._meta.verbose_name} {object_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la suppression: {str(e)}'
        })

@login_required
@user_passes_test(is_super_admin, login_url='/admin/')
@csrf_protect
def model_bulk_delete_view(request, app_label, model_name):
    """Vue pour supprimer plusieurs enregistrements"""
    
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return JsonResponse({
            'success': False,
            'error': f"Modèle {app_label}.{model_name} introuvable."
        })
    
    # Vérifier que c'est une requête AJAX
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'error': 'Cette action nécessite une requête AJAX.'
        })
    
    try:
        # Récupérer les IDs à supprimer
        ids_to_delete = request.POST.getlist('ids[]')
        
        if not ids_to_delete:
            return JsonResponse({
                'success': False,
                'error': 'Aucun élément sélectionné pour la suppression.'
            })
        
        # Supprimer les objets
        deleted_count, _ = model.objects.filter(pk__in=ids_to_delete).delete()
        
        # Log de l'action
        logger.info(f"Suppression en masse {model._meta.verbose_name_plural}: {deleted_count} éléments par {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} {model._meta.verbose_name_plural} supprimé(s) avec succès.'
        })
        
    except ProtectedError as e:
        # Nombre d'objets bloquants (toutes relations confondues)
        nb_blocking = 0
        try:
            nb_blocking = len(getattr(e, 'protected_objects', []) or [])
        except Exception:
            pass
        logger.warning(f"Suppression en masse bloquée (ProtectedError) {model._meta.verbose_name_plural}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': (
                "Suppression en masse impossible: certains éléments sont référencés par d'autres données protégées"
                + (f" (≈{nb_blocking} dépendances)" if nb_blocking else '')
                + ". Supprimez/retirez d'abord les éléments liés."
            )
        })
    except IntegrityError as e:
        logger.error(f"IntegrityError suppression en masse {model._meta.verbose_name_plural}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': "Suppression en masse impossible à cause d'une contrainte d'intégrité (FK/UNIQUE)."
        })
    except Exception as e:
        logger.error(f"Erreur lors de la suppression en masse {model._meta.verbose_name_plural}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la suppression: {str(e)}'
        })


@login_required
@user_passes_test(can_access_retards_paiement)
def eleves_retard_paiement(request):
    """Liste les élèves en retard: montants exigibles à date - (paiements + remises de l'année) > 0.
    Utilise l'année scolaire (septembre→août) et supporte la recherche/pagination.
    """
    today = timezone.localdate() if hasattr(timezone, 'localdate') else datetime.now().date()

    # Paramètres filtres
    annee = (request.GET.get('annee') or '').strip()
    search_query = request.GET.get('search', '').strip()

    # Déterminer l'année scolaire par défaut si non fournie
    # Forcer 2025-2026 comme année courante pour cohérence avec les données
    if not annee:
        annee = "2025-2026"

    # Période académique pour filtrer les remises
    try:
        annee_debut = int(annee.split('-')[0])
        periode_debut = datetime(annee_debut, 9, 1).date()
        periode_fin = datetime(annee_debut + 1, 8, 31).date()
    except Exception:
        periode_debut = datetime(today.year, 1, 1).date()
        periode_fin = datetime(today.year, 12, 31).date()

    # Base queryset
    qs = (
        EcheancierPaiement.objects
        .select_related('eleve', 'eleve__responsable_principal', 'eleve__responsable_secondaire', 'eleve__classe')
        .filter(annee_scolaire=annee)
    )

    # Restreindre la vue aux données de l'école de l'utilisateur.
    # Seul le superuser voit toutes les écoles; le staff et les rôles ADMIN sont filtrés.
    if not getattr(request.user, 'is_superuser', False):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')

    # Exigible à date (inscription + tranches échues)
    exigible_expr = (
        Case(When(date_echeance_inscription__lte=today, then=F('frais_inscription_du')), default=Value(0), output_field=DecimalField(max_digits=12, decimal_places=0))
        + Case(When(date_echeance_tranche_1__lte=today, then=F('tranche_1_due')), default=Value(0), output_field=DecimalField(max_digits=12, decimal_places=0))
        + Case(When(date_echeance_tranche_2__lte=today, then=F('tranche_2_due')), default=Value(0), output_field=DecimalField(max_digits=12, decimal_places=0))
        + Case(When(date_echeance_tranche_3__lte=today, then=F('tranche_3_due')), default=Value(0), output_field=DecimalField(max_digits=12, decimal_places=0))
    )

    # Remises validées pendant l'année scolaire (jusqu'à aujourd'hui)
    remises_expr = Coalesce(
        Sum(
            'eleve__paiements__remises__montant_remise',
            filter=(
                Q(eleve__paiements__statut='VALIDE') &
                Q(eleve__paiements__date_paiement__gte=periode_debut) &
                Q(eleve__paiements__date_paiement__lte=min(periode_fin, today))
            )
        ),
        Value(0),
        output_field=DecimalField(max_digits=12, decimal_places=0),
    )
    # Remises applicables ne doivent pas excéder l'exigible à date
    remises_applicables = Least(remises_expr, exigible_expr)

    # Montants payés (paiement anticipé accepté)
    paye_total = (F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'))
    # Paiements validés dans la période académique (même s'ils ne sont pas alloués dans l'échéancier)
    paiements_valides_total = Coalesce(
        Sum(
            'eleve__paiements__montant',
            filter=(
                Q(eleve__paiements__statut='VALIDE') &
                Q(eleve__paiements__date_paiement__gte=periode_debut) &
                Q(eleve__paiements__date_paiement__lte=min(periode_fin, today))
            )
        ),
        Value(0),
        output_field=DecimalField(max_digits=12, decimal_places=0),
    )
    # Choisir le payé effectif: le plus grand entre paiements validés et cumuls d'échéancier
    paye_effectif = Greatest(paiements_valides_total, paye_total)

    # Arriéré à date
    # arrears = max(0, exigible - (paye_total + remises_applicables))
    arrears_expr = ExpressionWrapper(exigible_expr - (paye_effectif + remises_applicables), output_field=DecimalField(max_digits=12, decimal_places=0))

    qs = qs.annotate(
        exigible_a_date=exigible_expr,
        remises_applicables=remises_applicables,
        paye_total=paye_effectif,
        arrears=arrears_expr,
    ).filter(arrears__gt=0).order_by('-arrears', 'eleve__nom', 'eleve__prenom')

    # Recherche simple sur élève et responsable principal
    if search_query:
        qs = qs.filter(
            Q(eleve__prenom__icontains=search_query) |
            Q(eleve__nom__icontains=search_query) |
            Q(eleve__matricule__icontains=search_query) |
            Q(eleve__responsable_principal__nom__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Adapter les objets pour le template existant (ajout d'attributs attendus)
    for obj in page_obj.object_list:
        # Confort: responsables et téléphones
        rp = getattr(obj.eleve, 'responsable_principal', None)
        rs = getattr(obj.eleve, 'responsable_secondaire', None)
        obj.responsable_principal = rp
        obj.responsable_secondaire = rs
        obj.telephone_principal = getattr(rp, 'telephone', None) if rp else None
        obj.telephone_secondaire = getattr(rs, 'telephone', None) if rs else None

        # Montant dû: le template lit désormais directement l'attribut annoté 'arrears'
        # obj.total_du = getattr(obj, 'arrears', 0)

        # Jours de retard approximatif: basé sur la dernière échéance échue
        dates = []
        try:
            if obj.date_echeance_inscription and obj.date_echeance_inscription <= today:
                dates.append(obj.date_echeance_inscription)
            if obj.date_echeance_tranche_1 and obj.date_echeance_tranche_1 <= today:
                dates.append(obj.date_echeance_tranche_1)
            if obj.date_echeance_tranche_2 and obj.date_echeance_tranche_2 <= today:
                dates.append(obj.date_echeance_tranche_2)
            if obj.date_echeance_tranche_3 and obj.date_echeance_tranche_3 <= today:
                dates.append(obj.date_echeance_tranche_3)
        except Exception:
            dates = []
        if dates:
            derniere_echeance = max(dates)
            obj.jours_retard = max(0, (today - derniere_echeance).days)
        else:
            obj.jours_retard = 0

    # Statistiques
    total_eleves_retard = qs.count()
    total_montant_du = qs.aggregate(
        s=Coalesce(
            Sum('arrears'),
            Value(Decimal('0'), output_field=DecimalField(max_digits=12, decimal_places=0)),
            output_field=DecimalField(max_digits=12, decimal_places=0),
        )
    )['s'] or Decimal('0')
    filtered_count = page_obj.paginator.count if search_query else None

    context = {
        'titre_page': 'Élèves en Retard de Paiement',
        'page_obj': page_obj,
        'search_query': search_query,
        'total_eleves_retard': total_eleves_retard,
        'total_montant_du': total_montant_du,
        'annee': annee,
        'periode_debut': periode_debut,
        'periode_fin': periode_fin,
        'filtered_count': filtered_count,
    }

    return render(request, 'administration/eleves_retard_paiement.html', context)


@login_required
@user_passes_test(can_access_retards_paiement)
def envoyer_rappel_paiement(request):
    """Vue pour envoyer des rappels de paiement par SMS/WhatsApp"""
    
    if request.method == 'POST':
        eleve_ids = request.POST.getlist('eleve_ids')
        message_type = request.POST.get('message_type', 'sms')
        message_personnalise = request.POST.get('message_personnalise', '')
        
        if not eleve_ids:
            return JsonResponse({'success': False, 'error': 'Aucun élève sélectionné'})
        
        # Générer le message par défaut si pas de message personnalisé
        if not message_personnalise:
            message_personnalise = (
                "Bonjour {nom_responsable},\n\n"
                "Nous vous informons que votre enfant {prenom_eleve} {nom_eleve} ({classe}) a un solde impayé de {montant_du} GNF.\n\n"
                "Merci de régulariser cette situation dans les plus brefs délais.\n\n"
                "École {nom_ecole}\nContact: {contact_ecole}"
            )

        # Préparer canal
        canal = 'WHATSAPP' if message_type.lower() == 'whatsapp' else 'SMS'

        from paiements.notifications import send_relance_notification

        # Restreindre la portée aux élèves de l'école de l'utilisateur (sauf superuser)
        base_qs = Eleve.objects.select_related('classe', 'classe__ecole', 'responsable_principal')
        if not getattr(request.user, 'is_superuser', False):
            base_qs = filter_by_user_school(base_qs, request.user, 'classe__ecole')

        envoyes = 0
        for eleve_id in eleve_ids:
            try:
                eleve = base_qs.get(id=eleve_id)
            except Eleve.DoesNotExist:
                continue

            # total dû (ne pas filtrer sur un @property au niveau ORM)
            total_du = Decimal('0')
            try:
                echeancier = EcheancierPaiement.objects.get(eleve=eleve)
                if echeancier.solde_restant > 0:
                    total_du = echeancier.solde_restant
            except EcheancierPaiement.DoesNotExist:
                pass

            # Préparer destinataires: principal et secondaire si disponibles
            destinataires = []
            if getattr(eleve, 'responsable_principal', None) and eleve.responsable_principal.telephone:
                destinataires.append((eleve.responsable_principal.nom, eleve.responsable_principal.telephone))
            if getattr(eleve, 'responsable_secondaire', None) and eleve.responsable_secondaire.telephone:
                destinataires.append((eleve.responsable_secondaire.nom, eleve.responsable_secondaire.telephone))

            if not destinataires:
                logger.warning(f"Aucun numéro pour élève {eleve.id} — relance non envoyée")
                continue

            for nom_resp, numero in destinataires:
                message_final = message_personnalise.format(
                    nom_responsable=nom_resp or 'Responsable',
                    prenom_eleve=eleve.prenom,
                    nom_eleve=eleve.nom,
                    classe=eleve.classe.nom if eleve.classe else 'Non définie',
                    montant_du=f"{int(total_du):,}".replace(',', ' '),
                    nom_ecole=eleve.classe.ecole.nom if eleve.classe and eleve.classe.ecole else 'École',
                    contact_ecole="Contactez l'administration",
                )

                # Créer une Relance et envoyer via helper centralisé pour ce destinataire
                relance = Relance(
                    eleve=eleve,
                    canal=canal,
                    message=message_final,
                    solde_estime=total_du,
                    cree_par=request.user if request.user.is_authenticated else None,
                    statut='ENREGISTREE',
                )
                relance.save()
                try:
                    send_relance_notification(relance, to_number=numero)
                    relance.statut = 'ENVOYEE'
                    relance.save(update_fields=['statut'])
                    envoyes += 1
                except Exception as e:
                    relance.statut = 'ECHEC'
                    relance.save(update_fields=['statut'])
                    logger.error(f"Échec envoi relance pour élève {eleve.id} vers {numero}: {e}")

        return JsonResponse({'success': True, 'message': f'{envoyes} relance(s) envoyée(s)'})
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})
