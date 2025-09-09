from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .forms import ComptableCreationForm
from .models import Profil
from .decorators import admin_or_directeur_required
from eleves.models import Ecole


def _est_admin(user):
    """Vrai si superuser ou profil ADMIN avec droit de gestion utilisateurs."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profil = getattr(user, 'profil', None)
    return bool(profil and profil.role == 'ADMIN' and profil.peut_gerer_utilisateurs)


@login_required
@user_passes_test(_est_admin)
def comptable_create_view(request):
    """Création d'un compte Comptable (User + Profil) via formulaire dédié."""
    # Si ce n'est pas un superuser, il doit avoir une école définie
    if not request.user.is_superuser:
        profil_user = getattr(request.user, 'profil', None)
        if not (profil_user and profil_user.ecole_id):
            # Page dédiée d'accès refusé (403)
            return render(request, 'utilisateurs/acces_refuse_ecole.html', status=403)
    if request.method == 'POST':
        form = ComptableCreationForm(request.POST, request=request)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Compte comptable créé avec succès: {user.username}"
            )
            return redirect('home')
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = ComptableCreationForm(request=request)

    return render(request, 'utilisateurs/comptable_form.html', {
        'form': form,
        'title': "Créer un comptable",
    })


@login_required
@require_POST
def changer_ecole_view(request):
    """Vue pour changer l'école sélectionnée (super admins uniquement)"""
    if not request.user.is_superuser:
        messages.error(request, "Accès refusé.")
        return redirect('home')
    
    ecole_id = request.POST.get('ecole_id')
    
    if ecole_id:
        try:
            ecole = Ecole.objects.get(id=ecole_id, statut='ACTIVE')
            request.session['ecole_selectionnee'] = ecole.id
            messages.success(request, f"École '{ecole.nom}' sélectionnée.")
        except Ecole.DoesNotExist:
            messages.error(request, "École non trouvée ou inactive.")
    else:
        # Désélectionner l'école (mode global)
        if 'ecole_selectionnee' in request.session:
            del request.session['ecole_selectionnee']
        messages.info(request, "Mode global activé - toutes les écoles.")
    
    # Rediriger vers la page précédente ou l'accueil
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
@admin_or_directeur_required
def gestion_utilisateurs_view(request):
    """Vue pour la gestion des utilisateurs par école"""
    # Récupérer les utilisateurs selon le contexte
    if request.user.is_superuser:
        # Super admin voit tous les utilisateurs
        if hasattr(request, 'ecole_courante') and request.ecole_courante:
            profils = Profil.objects.filter(ecole=request.ecole_courante)
        else:
            profils = Profil.objects.all()
    else:
        # Admin/Directeur ne voit que les utilisateurs de son école
        try:
            profil_user = request.user.profil
            profils = Profil.objects.filter(ecole=profil_user.ecole)
        except Profil.DoesNotExist:
            messages.error(request, "Profil utilisateur non configuré.")
            return redirect('home')
    
    # Recherche
    search = request.GET.get('search', '')
    if search:
        profils = profils.filter(
            Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Filtrage par rôle
    role_filter = request.GET.get('role', '')
    if role_filter:
        profils = profils.filter(role=role_filter)
    
    # Pagination
    paginator = Paginator(profils.select_related('user', 'ecole'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'role_filter': role_filter,
        'roles_choices': Profil.ROLE_CHOICES,
        'titre_page': 'Gestion des utilisateurs',
    }
    
    return render(request, 'utilisateurs/gestion_utilisateurs.html', context)


@login_required
def profil_view(request):
    """Vue pour afficher et modifier le profil utilisateur"""
    try:
        profil = request.user.profil
    except Profil.DoesNotExist:
        messages.error(request, "Profil utilisateur non configuré.")
        return redirect('home')
    
    context = {
        'profil': profil,
        'titre_page': 'Mon profil',
    }
    
    return render(request, 'utilisateurs/profil.html', context)


@login_required
@user_passes_test(_est_admin)
def comptable_list_view(request):
    """Liste paginée des comptes Comptables, filtrable par école et recherche."""
    qs = Profil.objects.select_related('user', 'ecole').filter(role='COMPTABLE')

    ecole_id = request.GET.get('ecole')
    q = request.GET.get('q')
    # Isolation par école pour non-superadmins
    if not request.user.is_superuser:
        profil_user = getattr(request.user, 'profil', None)
        if profil_user and profil_user.ecole_id:
            qs = qs.filter(ecole_id=profil_user.ecole_id)
            # Forcer le filtre d'école à celle de l'utilisateur
            ecole_id = str(profil_user.ecole_id)
        else:
            # Pas d'école: aucun résultat
            qs = qs.none()

    if ecole_id:
        qs = qs.filter(ecole_id=ecole_id)
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
            | Q(telephone__icontains=q)
        )

    paginator = Paginator(qs.order_by('user__username'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Restreindre la liste des écoles à celle de l'utilisateur si non superuser
    if request.user.is_superuser:
        ecoles = Ecole.objects.all().order_by('nom') if hasattr(Ecole, 'nom') else Ecole.objects.all()
    else:
        profil_user = getattr(request.user, 'profil', None)
        base = Ecole.objects.all()
        base = base.order_by('nom') if hasattr(Ecole, 'nom') else base
        if profil_user and profil_user.ecole_id:
            ecoles = base.filter(pk=profil_user.ecole_id)
        else:
            ecoles = base.none()

    return render(request, 'utilisateurs/comptable_list.html', {
        'page_obj': page_obj,
        'ecoles': ecoles,
        'filtre_ecole': ecole_id or '',
        'query': q or '',
        'title': "Comptables",
    })
