from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q

from .forms import ComptableCreationForm
from .models import Profil
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
            messages.error(request, "Votre profil n'est associé à aucune école. Veuillez contacter l'administrateur pour configurer votre école avant de créer un comptable.")
            return redirect('home')
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
