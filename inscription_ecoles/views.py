from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView, ListView
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import models
from django.core.paginator import Paginator
from django.db.models import Q
from .models import DemandeInscriptionEcole, ConfigurationEcole, TemplateDocument, ClasseInscription, EcheancierInscription
from .forms import DemandeInscriptionForm, ConfigurationEcoleForm, DemandeInscriptionCompleteForm, ClasseInscriptionFormSet, EcheancierInscriptionForm
from eleves.models import Ecole
from utilisateurs.models import Profil
from utilisateurs.decorators import admin_or_directeur_required
import json


def inscription_ecole_complete(request):
    """Vue pour l'inscription complète d'une école avec classes et échéances"""
    if request.method == 'POST':
        form = DemandeInscriptionCompleteForm(request.POST, request.FILES)
        formset_classes = ClasseInscriptionFormSet(request.POST, prefix='classes')
        form_echeancier = EcheancierInscriptionForm(request.POST, prefix='echeancier')
        
        if form.is_valid() and formset_classes.is_valid() and form_echeancier.is_valid():
            # Sauvegarder la demande d'inscription
            demande = form.save()
            
            # Sauvegarder l'échéancier
            echeancier = form_echeancier.save(commit=False)
            echeancier.demande_inscription = demande
            echeancier.save()
            
            # Sauvegarder les classes
            formset_classes.instance = demande
            formset_classes.save()
            
            # Envoyer un email de confirmation
            try:
                nb_classes = demande.classes_prevues.count()
                send_mail(
                    'Demande d\'inscription reçue - École Moderne',
                    f'Bonjour {demande.prenom_demandeur},\n\n'
                    f'Nous avons bien reçu votre demande d\'inscription pour l\'école "{demande.nom_ecole}".\n'
                    f'Votre demande comprend {nb_classes} classe(s) et un échéancier personnalisé.\n'
                    f'Votre demande sera traitée dans les plus brefs délais.\n\n'
                    f'Cordialement,\nL\'équipe École Moderne',
                    settings.DEFAULT_FROM_EMAIL,
                    [demande.email_demandeur],
                    fail_silently=True,
                )
            except Exception:
                pass
            
            messages.success(request, 'Votre demande d\'inscription complète a été envoyée avec succès!')
            return redirect('inscription_merci')
    else:
        form = DemandeInscriptionCompleteForm()
        formset_classes = ClasseInscriptionFormSet(prefix='classes')
        form_echeancier = EcheancierInscriptionForm(prefix='echeancier')
    
    context = {
        'form': form,
        'formset_classes': formset_classes,
        'form_echeancier': form_echeancier,
    }
    return render(request, 'inscription_ecoles/inscription_complete.html', context)


class InscriptionEcoleView(CreateView):
    """Vue pour l'inscription simple d'une école (ancienne version)"""
    model = DemandeInscriptionEcole
    form_class = DemandeInscriptionForm
    template_name = 'inscription_ecoles/inscription.html'
    success_url = '/inscription/merci/'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Envoyer un email de confirmation
        try:
            send_mail(
                'Demande d\'inscription reçue - École Moderne',
                f'Bonjour {form.instance.prenom_demandeur},\n\n'
                f'Nous avons bien reçu votre demande d\'inscription pour l\'école "{form.instance.nom_ecole}".\n'
                f'Votre demande sera traitée dans les plus brefs délais.\n\n'
                f'Cordialement,\nL\'équipe École Moderne',
                settings.DEFAULT_FROM_EMAIL,
                [form.instance.email_demandeur],
                fail_silently=True,
            )
        except Exception:
            pass
        
        messages.success(self.request, 'Votre demande d\'inscription a été envoyée avec succès!')
        return response


def inscription_merci(request):
    """Page de remerciement après inscription"""
    return render(request, 'inscription_ecoles/merci.html')


@login_required
def tableau_bord_ecole(request):
    """Tableau de bord pour une école"""
    try:
        ecole = request.user.profil.ecole
        if not ecole:
            messages.error(request, 'Aucune école associée à votre compte.')
            return redirect('home')
        
        # Statistiques de base
        stats = {
            'nb_eleves': ecole.classes.aggregate(
                total=models.Count('eleves')
            )['total'] or 0,
            'nb_classes': ecole.classes.count(),
            'nb_enseignants': ecole.profils.filter(role='ENSEIGNANT').count(),
        }
        
        context = {
            'ecole': ecole,
            'stats': stats,
        }
        return render(request, 'inscription_ecoles/tableau_bord.html', context)
        
    except AttributeError:
        messages.error(request, 'Profil utilisateur non configuré.')
        return redirect('home')


@login_required
def configuration_ecole(request):
    """Configuration de l'école"""
    try:
        ecole = request.user.profil.ecole
        if not ecole:
            messages.error(request, 'Aucune école associée à votre compte.')
            return redirect('home')
        
        config, created = ConfigurationEcole.objects.get_or_create(ecole=ecole)
        
        if request.method == 'POST':
            form = ConfigurationEcoleForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                messages.success(request, 'Configuration mise à jour avec succès!')
                return redirect('configuration_ecole')
        else:
            form = ConfigurationEcoleForm(instance=config)
        
        context = {
            'ecole': ecole,
            'form': form,
            'config': config,
        }
        return render(request, 'inscription_ecoles/configuration.html', context)
        
    except AttributeError:
        messages.error(request, 'Profil utilisateur non configuré.')
        return redirect('home')


@login_required
def personnaliser_documents(request):
    """Personnalisation des documents PDF"""
    try:
        ecole = request.user.profil.ecole
        if not ecole:
            messages.error(request, 'Aucune école associée à votre compte.')
            return redirect('home')
        
        # Récupérer les templates existants pour cette école
        templates = TemplateDocument.objects.filter(ecole=ecole, est_actif=True)
        
        # Templates par défaut si aucun template personnalisé
        templates_defaut = TemplateDocument.objects.filter(
            ecole__isnull=True, 
            est_par_defaut=True,
            est_actif=True
        )
        
        context = {
            'ecole': ecole,
            'templates': templates,
            'templates_defaut': templates_defaut,
        }
        return render(request, 'inscription_ecoles/personnaliser_documents.html', context)
        
    except AttributeError:
        messages.error(request, 'Profil utilisateur non configuré.')
        return redirect('home')


@csrf_exempt
def apercu_document(request):
    """Génère un aperçu d'un document personnalisé"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            type_document = data.get('type_document')
            contenu_html = data.get('contenu_html')
            styles_css = data.get('styles_css', '')
            
            # Données d'exemple pour l'aperçu
            donnees_exemple = {
                'FICHE_INSCRIPTION': {
                    'ecole_nom': 'École Exemple',
                    'eleve_nom': 'DUPONT',
                    'eleve_prenom': 'Jean',
                    'classe': '6ème année',
                },
                'RECU_PAIEMENT': {
                    'numero_recu': 'REC-000001',
                    'eleve_nom': 'DUPONT Jean',
                    'montant': '500,000 GNF',
                    'date': '08/09/2025',
                },
                'BULLETIN_NOTES': {
                    'eleve_nom': 'DUPONT Jean',
                    'classe': '6ème année',
                    'trimestre': '1er Trimestre',
                    'moyenne': '14.5/20',
                },
            }
            
            donnees = donnees_exemple.get(type_document, {})
            
            # Remplacer les variables dans le HTML
            html_final = contenu_html
            for cle, valeur in donnees.items():
                html_final = html_final.replace(f'{{{{{cle}}}}}', str(valeur))
            
            return JsonResponse({
                'success': True,
                'html': html_final,
                'css': styles_css
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})


# Vues d'administration pour les super-utilisateurs
@login_required
def admin_demandes_inscription(request):
    """Liste des demandes d'inscription (admin seulement)"""
    if not request.user.is_superuser:
        messages.error(request, 'Accès non autorisé.')
        return redirect('home')
    
    demandes = DemandeInscriptionEcole.objects.all().order_by('-date_demande')
    
    context = {
        'demandes': demandes,
    }
    return render(request, 'inscription_ecoles/admin_demandes.html', context)


@login_required
def traiter_demande_inscription(request, demande_id):
    """Traiter une demande d'inscription"""
    if not request.user.is_superuser:
        messages.error(request, 'Accès non autorisé.')
        return redirect('home')
    
    demande = get_object_or_404(DemandeInscriptionEcole, id=demande_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'creer_compte':
            # Créer directement le compte utilisateur
            import secrets
            import string
            
            # Générer nom d'utilisateur unique
            base_username = f"admin_{demande.nom_ecole.lower().replace(' ', '_').replace('-', '_')}"
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            
            # Générer mot de passe temporaire
            password_temp = User.objects.make_random_password(length=12)
            
            # Créer l'utilisateur
            user = User.objects.create_user(
                username=username,
                email=demande.email_demandeur,
                first_name=demande.prenom_demandeur,
                last_name=demande.nom_demandeur,
                password=password_temp
            )
            
            # Créer le profil sans école (l'utilisateur créera son école)
            Profil.objects.create(
                user=user,
                role="ADMIN",
                telephone=demande.telephone_demandeur,
                ecole=None,  # Pas d'école assignée pour le moment
                peut_valider_paiements=True,
                peut_valider_depenses=True,
                peut_generer_rapports=True,
                peut_gerer_utilisateurs=True,
                actif=True
            )
            
            # Mettre à jour la demande
            demande.statut = 'APPROUVEE'
            demande.utilisateur_cree = user
            demande.traite_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            
            # Envoyer email avec les identifiants
            try:
                send_mail(
                    'École approuvée - Identifiants de connexion',
                    f'Bonjour {demande.prenom_demandeur},\n\n'
                    f'Votre demande pour l\'école "{demande.nom_ecole}" a été approuvée!\n\n'
                    f'Vos identifiants de connexion:\n'
                    f'Nom d\'utilisateur: {username}\n'
                    f'Mot de passe temporaire: {password_temp}\n\n'
                    f'Connectez-vous sur: http://127.0.0.1:8001/\n'
                    f'Après connexion, vous pourrez créer votre établissement scolaire.\n\n'
                    f'IMPORTANT: Changez votre mot de passe lors de votre première connexion.\n\n'
                    f'Cordialement,\nL\'équipe École Moderne',
                    settings.DEFAULT_FROM_EMAIL,
                    [demande.email_demandeur],
                    fail_silently=True,
                )
            except Exception:
                pass
            
            messages.success(request, f'Compte créé: {username}. Identifiants envoyés par email.')
        
        elif action == 'approuver':
            # Créer directement l'école avec classes et échéances
            username = f"admin_{demande.nom_ecole.lower().replace(' ', '_')}"
            counter = 1
            base_username = username
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            
            password_temp = User.objects.make_random_password()
            user = User.objects.create_user(
                username=username,
                email=demande.email_demandeur,
                first_name=demande.prenom_demandeur,
                last_name=demande.nom_demandeur,
                password=password_temp
            )
            
            # Créer l'école
            ecole = Ecole.objects.create(
                nom=demande.nom_ecole,
                nom_complet=demande.nom_complet_ecole,
                type_ecole=demande.type_ecole,
                adresse=demande.adresse_ecole,
                ville=demande.ville,
                prefecture=demande.prefecture,
                telephone=demande.telephone_ecole,
                email=demande.email_ecole,
                site_web=demande.site_web,
                directeur=demande.nom_directeur,
                directeur_telephone=demande.telephone_directeur,
                numero_autorisation=demande.numero_autorisation,
                date_autorisation=demande.date_autorisation,
                utilisateur_admin=user,
                statut='ACTIVE'
            )
            
            # Copier le logo si fourni
            if demande.logo_ecole:
                ecole.logo = demande.logo_ecole
                ecole.save()
            
            # Créer les classes à partir des classes d'inscription
            from eleves.models import Classe
            classes_creees = []
            for classe_inscription in demande.classes_prevues.all():
                classe = Classe.objects.create(
                    ecole=ecole,
                    nom=classe_inscription.nom,
                    niveau=classe_inscription.niveau,
                    code_matricule=classe_inscription.code_matricule,
                    annee_scolaire=demande.echeancier_prevu.annee_scolaire if hasattr(demande, 'echeancier_prevu') else '2024-2025',
                    capacite_max=classe_inscription.capacite_max
                )
                classes_creees.append(classe)
            
            # Créer les grilles tarifaires à partir des classes d'inscription
            if hasattr(demande, 'echeancier_prevu'):
                from paiements.models import GrilleTarifaire
                for classe_inscription in demande.classes_prevues.all():
                    classe = classes_creees[0]  # Associer à la première classe créée pour l'exemple
                    GrilleTarifaire.objects.create(
                        ecole=ecole,
                        classe=classe,
                        annee_scolaire=demande.echeancier_prevu.annee_scolaire,
                        frais_inscription=classe_inscription.frais_inscription,
                        tranche_1=classe_inscription.tranche_1,
                        tranche_2=classe_inscription.tranche_2,
                        tranche_3=classe_inscription.tranche_3
                    )
            
            # Créer le profil administrateur pour l'école
            Profil.objects.create(
                user=user,
                role='ADMIN',
                telephone=demande.telephone_demandeur,
                ecole=ecole,
                peut_valider_paiements=True,
                peut_valider_depenses=True,
                peut_generer_rapports=True,
                peut_gerer_utilisateurs=True,
                actif=True
            )
            
            # Créer la configuration par défaut
            ConfigurationEcole.objects.create(ecole=ecole)
            
            # Mettre à jour la demande
            demande.statut = 'APPROUVEE'
            demande.ecole_creee = ecole
            demande.traite_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            
            # Envoyer email avec les identifiants
            try:
                nb_classes = len(classes_creees)
                send_mail(
                    'École approuvée - Identifiants de connexion',
                    f'Bonjour {demande.prenom_demandeur},\n\n'
                    f'Votre école "{ecole.nom}" a été approuvée!\n'
                    f'{nb_classes} classe(s) ont été créées avec leurs tarifications.\n\n'
                    f'Identifiants de connexion:\n'
                    f'Nom d\'utilisateur: {username}\n'
                    f'Mot de passe temporaire: {password_temp}\n\n'
                    f'Veuillez changer votre mot de passe lors de votre première connexion.\n\n'
                    f'Cordialement,\nL\'équipe École Moderne',
                    settings.DEFAULT_FROM_EMAIL,
                    [demande.email_demandeur],
                    fail_silently=True,
                )
            except Exception:
                pass
            
            messages.success(request, f'École "{ecole.nom}" créée avec {len(classes_creees)} classe(s)! Identifiants envoyés par email.')
            
        elif action == 'rejeter':
            motif = request.POST.get('motif_rejet')
            demande.statut = 'REJETEE'
            demande.motif_rejet = motif
            demande.traite_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            
            messages.success(request, 'Demande rejetée.')
        
        return redirect('admin_demandes_inscription')
    
    context = {
        'demande': demande,
    }
    return render(request, 'inscription_ecoles/traiter_demande.html', context)
