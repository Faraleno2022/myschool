from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import DemandeInscriptionEcole, ConfigurationEcole
from eleves.models import Ecole
from utilisateurs.models import Profil


@login_required
@csrf_protect
def creer_etablissement(request):
    """Vue pour créer un établissement après connexion utilisateur"""
    
    # Vérifier que l'utilisateur a un profil mais pas d'école
    try:
        profil = request.user.profil
        if profil.ecole:
            messages.info(request, 'Vous avez déjà un établissement associé.')
            return redirect('tableau_bord_ecole')
    except:
        messages.error(request, 'Profil utilisateur non trouvé.')
        return redirect('home')
    
    # Récupérer la demande d'inscription liée à cet utilisateur
    try:
        demande = DemandeInscriptionEcole.objects.get(utilisateur_cree=request.user)
    except DemandeInscriptionEcole.DoesNotExist:
        messages.error(request, 'Aucune demande d\'inscription trouvée pour votre compte.')
        return redirect('home')
    
    if request.method == 'POST':
        # Récupérer les données du formulaire
        nom_ecole = request.POST.get('nom_ecole', '').strip()
        nom_complet = request.POST.get('nom_complet', '').strip()
        type_ecole = request.POST.get('type_ecole')
        adresse = request.POST.get('adresse', '').strip()
        ville = request.POST.get('ville', '').strip()
        prefecture = request.POST.get('prefecture', '').strip()
        telephone = request.POST.get('telephone', '').strip()
        email = request.POST.get('email', '').strip()
        site_web = request.POST.get('site_web', '').strip()
        directeur = request.POST.get('directeur', '').strip()
        directeur_telephone = request.POST.get('directeur_telephone', '').strip()
        
        # Validation
        if not all([nom_ecole, type_ecole, adresse, ville, prefecture, telephone, email, directeur]):
            messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
            return render(request, 'inscription_ecoles/creer_etablissement.html', {
                'demande': demande
            })
        
        try:
            # Générer un slug unique
            base_slug = nom_ecole.lower().replace(' ', '-').replace('_', '-')
            # Nettoyer le slug
            import re
            base_slug = re.sub(r'[^a-z0-9-]', '', base_slug)
            slug = base_slug
            counter = 1
            while Ecole.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Créer l'école
            ecole = Ecole.objects.create(
                nom=nom_ecole,
                nom_complet=nom_complet or nom_ecole,
                slug=slug,
                type_ecole=type_ecole,
                adresse=adresse,
                ville=ville,
                prefecture=prefecture,
                telephone=telephone,
                email=email,
                site_web=site_web if site_web else None,
                directeur=directeur,
                directeur_telephone=directeur_telephone if directeur_telephone else None,
                utilisateur_admin=request.user,
                statut='ACTIVE'
            )
            
            # Associer l'école au profil utilisateur
            profil.ecole = ecole
            profil.save()
            
            # Créer la configuration par défaut
            ConfigurationEcole.objects.create(ecole=ecole)
            
            # Mettre à jour la demande
            demande.ecole_creee = ecole
            demande.save()
            
            # Envoyer email de confirmation
            try:
                send_mail(
                    'Établissement créé avec succès',
                    f'Bonjour {request.user.first_name},\n\n'
                    f'Votre établissement "{ecole.nom}" a été créé avec succès!\n\n'
                    f'Vous pouvez maintenant accéder à votre tableau de bord pour commencer '
                    f'à gérer vos élèves, classes, paiements et autres fonctionnalités.\n\n'
                    f'Cordialement,\nL\'équipe École Moderne',
                    settings.DEFAULT_FROM_EMAIL,
                    [request.user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            
            messages.success(request, f'Établissement "{ecole.nom}" créé avec succès!')
            return redirect('inscription_ecoles:tableau_bord_ecole')
            
        except Exception as e:
            messages.error(request, f'Erreur lors de la création: {str(e)}')
    
    context = {
        'demande': demande,
        'user': request.user
    }
    return render(request, 'inscription_ecoles/creer_etablissement.html', context)


@login_required
def verifier_statut_etablissement(request):
    """Vérifier si l'utilisateur doit créer son établissement"""
    try:
        profil = request.user.profil
        if not profil.ecole:
            # L'utilisateur n'a pas d'école, rediriger vers création
            return redirect('inscription_ecoles:creer_etablissement')
        else:
            # L'utilisateur a déjà une école
            return redirect('inscription_ecoles:tableau_bord_ecole')
    except:
        messages.error(request, 'Profil utilisateur non configuré.')
        return redirect('home')
