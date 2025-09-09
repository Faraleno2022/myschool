from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import DemandeInscriptionEcole, ConfigurationEcole
from eleves.models import Ecole
from utilisateurs.models import Profil
import secrets
import string


@csrf_protect
def creer_compte_ecole(request):
    """Vue pour créer un compte école avec un code d'accès"""
    if request.method == 'POST':
        code_acces = request.POST.get('code_acces', '').strip().upper()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        # Validation des champs
        if not code_acces:
            messages.error(request, 'Le code d\'accès est requis.')
            return render(request, 'inscription_ecoles/creer_compte.html')
        
        if not username:
            messages.error(request, 'Le nom d\'utilisateur est requis.')
            return render(request, 'inscription_ecoles/creer_compte.html')
        
        if len(password) < 8:
            messages.error(request, 'Le mot de passe doit contenir au moins 8 caractères.')
            return render(request, 'inscription_ecoles/creer_compte.html')
        
        if password != password_confirm:
            messages.error(request, 'Les mots de passe ne correspondent pas.')
            return render(request, 'inscription_ecoles/creer_compte.html')
        
        # Vérifier si le nom d'utilisateur existe déjà
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Ce nom d\'utilisateur existe déjà.')
            return render(request, 'inscription_ecoles/creer_compte.html')
        
        # Vérifier le code d'accès
        try:
            demande = DemandeInscriptionEcole.objects.get(
                code_acces=code_acces,
                statut='APPROUVEE'
            )
            
            # Vérifier que l'école n'a pas déjà été créée
            if hasattr(demande, 'ecole_creee') and demande.ecole_creee:
                messages.error(request, 'Ce code d\'accès a déjà été utilisé.')
                return render(request, 'inscription_ecoles/creer_compte.html')
            
        except DemandeInscriptionEcole.DoesNotExist:
            messages.error(request, 'Code d\'accès invalide ou expiré.')
            return render(request, 'inscription_ecoles/creer_compte.html')
        
        try:
            # Créer l'utilisateur
            user = User.objects.create_user(
                username=username,
                email=demande.email_demandeur,
                first_name=demande.prenom_demandeur,
                last_name=demande.nom_demandeur,
                password=password
            )
            
            # Générer un slug unique pour l'école
            base_slug = demande.nom_ecole.lower().replace(' ', '-')
            slug = base_slug
            counter = 1
            while Ecole.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Créer l'école
            ecole = Ecole.objects.create(
                nom=demande.nom_ecole,
                nom_complet=demande.nom_complet_ecole or demande.nom_ecole,
                slug=slug,
                type_ecole=demande.type_ecole,
                adresse=demande.adresse_ecole,
                ville=demande.ville,
                prefecture=demande.prefecture,
                telephone=demande.telephone_ecole,
                email=demande.email_ecole,
                site_web=demande.site_web,
                directeur=demande.nom_directeur,
                directeur_telephone=demande.telephone_directeur,
                numero_autorisation=getattr(demande, 'numero_autorisation', ''),
                date_autorisation=getattr(demande, 'date_autorisation', None),
                utilisateur_admin=user,
                statut='ACTIVE'
            )
            
            # Copier le logo si fourni
            if hasattr(demande, 'logo_ecole') and demande.logo_ecole:
                ecole.logo = demande.logo_ecole
                ecole.save()
            
            # Créer le profil administrateur
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
            demande.ecole_creee = ecole
            demande.compte_cree_le = timezone.now()
            demande.save()
            
            # Connecter automatiquement l'utilisateur
            login(request, user)
            
            # Envoyer email de confirmation
            try:
                send_mail(
                    'Compte école créé avec succès',
                    f'Bonjour {user.first_name},\n\n'
                    f'Votre compte pour l\'école "{ecole.nom}" a été créé avec succès!\n\n'
                    f'Vous pouvez maintenant accéder à votre tableau de bord.\n\n'
                    f'Cordialement,\nL\'équipe École Moderne',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            
            messages.success(request, f'Compte créé avec succès pour l\'école "{ecole.nom}"!')
            return redirect('tableau_bord_ecole')
            
        except Exception as e:
            messages.error(request, f'Erreur lors de la création du compte: {str(e)}')
            return render(request, 'inscription_ecoles/creer_compte.html')
    
    return render(request, 'inscription_ecoles/creer_compte.html')


def verifier_code_acces(request):
    """API pour vérifier un code d'accès en temps réel"""
    if request.method == 'POST':
        import json
        from django.http import JsonResponse
        
        try:
            data = json.loads(request.body)
            code_acces = data.get('code_acces', '').strip().upper()
            
            if not code_acces:
                return JsonResponse({'valid': False, 'message': 'Code requis'})
            
            try:
                demande = DemandeInscriptionEcole.objects.get(
                    code_acces=code_acces,
                    statut='APPROUVEE'
                )
                
                # Vérifier que l'école n'a pas déjà été créée
                if hasattr(demande, 'ecole_creee') and demande.ecole_creee:
                    return JsonResponse({
                        'valid': False, 
                        'message': 'Code déjà utilisé'
                    })
                
                return JsonResponse({
                    'valid': True,
                    'ecole_nom': demande.nom_ecole,
                    'demandeur': f"{demande.prenom_demandeur} {demande.nom_demandeur}"
                })
                
            except DemandeInscriptionEcole.DoesNotExist:
                return JsonResponse({
                    'valid': False,
                    'message': 'Code invalide'
                })
                
        except Exception as e:
            return JsonResponse({
                'valid': False,
                'message': 'Erreur de vérification'
            })
    
    return JsonResponse({'valid': False, 'message': 'Méthode non autorisée'})
