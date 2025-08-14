from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    Depense, CategorieDepense, Fournisseur, 
    PieceJustificative, BudgetAnnuel, HistoriqueDepense
)
from .forms import (
    DepenseForm, CategorieDepenseForm, FournisseurForm,
    PieceJustificativeForm, BudgetAnnuelForm
)
from utilisateurs.utils import user_is_admin, user_school
from utilisateurs.permissions import can_add_expenses, can_modify_expenses, can_delete_expenses, can_validate_expenses

@login_required
def tableau_bord(request):
    """Tableau de bord principal du module dépenses"""
    # Base filtrée par école pour non-admin
    base_qs = Depense.objects.all()
    if not user_is_admin(request.user):
        base_qs = base_qs.filter(cree_par__profil__ecole=user_school(request.user))
    # Statistiques générales
    total_depenses = base_qs.count()
    depenses_validees = base_qs.filter(statut='VALIDEE').count()
    depenses_payees = base_qs.filter(statut='PAYEE').count()
    depenses_en_attente = base_qs.filter(statut='EN_ATTENTE').count()
    
    # Montants
    montant_total = base_qs.aggregate(
        total=Sum('montant_ttc')
    )['total'] or Decimal('0')
    
    montant_paye = base_qs.filter(statut='PAYEE').aggregate(
        total=Sum('montant_ttc')
    )['total'] or Decimal('0')
    
    montant_en_attente = base_qs.filter(statut='EN_ATTENTE').aggregate(
        total=Sum('montant_ttc')
    )['total'] or Decimal('0')
    
    # Dépenses récentes
    depenses_recentes = base_qs.select_related(
        'categorie', 'fournisseur', 'cree_par'
    ).order_by('-date_creation')[:10]
    
    # Dépenses en retard
    depenses_en_retard = base_qs.filter(
        date_echeance__lt=timezone.now().date(),
        statut__in=['VALIDEE', 'EN_ATTENTE']
    ).count()
    
    # Statistiques par catégorie
    # Statistiques par catégorie (portée approximée si non-admin)
    stats_categories = CategorieDepense.objects.filter(actif=True)
    # NOTE: Les annotations globales peuvent inclure des dépenses d'autres écoles.
    # Pour éviter toute fuite de données, on ne joint pas de totaux précis ici pour les non-admins.
    if user_is_admin(request.user):
        stats_categories = stats_categories.annotate(
            nb_depenses=Count('depenses'),
            montant_total=Sum('depenses__montant_ttc')
        )
    
    context = {
        'total_depenses': total_depenses,
        'depenses_validees': depenses_validees,
        'depenses_payees': depenses_payees,
        'depenses_en_attente': depenses_en_attente,
        'montant_total': montant_total,
        'montant_paye': montant_paye,
        'montant_en_attente': montant_en_attente,
        'depenses_recentes': depenses_recentes,
        'depenses_en_retard': depenses_en_retard,
        'stats_categories': stats_categories,
    }
    
    return render(request, 'depenses/tableau_bord.html', context)

@login_required
def liste_depenses(request):
    """Liste des dépenses avec filtres et pagination"""
    depenses = Depense.objects.select_related(
        'categorie', 'fournisseur', 'cree_par', 'valide_par'
    ).order_by('-date_creation')
    if not user_is_admin(request.user):
        depenses = depenses.filter(cree_par__profil__ecole=user_school(request.user))
    
    # Filtres
    statut_filtre = request.GET.get('statut')
    if statut_filtre:
        depenses = depenses.filter(statut=statut_filtre)
    
    categorie_filtre = request.GET.get('categorie')
    if categorie_filtre:
        depenses = depenses.filter(categorie_id=categorie_filtre)
    
    fournisseur_filtre = request.GET.get('fournisseur')
    if fournisseur_filtre:
        depenses = depenses.filter(fournisseur_id=fournisseur_filtre)
    
    recherche = request.GET.get('recherche')
    if recherche:
        depenses = depenses.filter(
            Q(libelle__icontains=recherche) |
            Q(numero_facture__icontains=recherche) |
            Q(description__icontains=recherche)
        )
    
    # Pagination
    paginator = Paginator(depenses, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Totaux pour les filtres appliqués
    totaux = {
        'nombre_total': depenses.count(),
        'montant_total': depenses.aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or Decimal('0'),
        'nombre_en_attente': depenses.filter(statut='EN_ATTENTE').count(),
        'montant_en_attente': depenses.filter(statut='EN_ATTENTE').aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or Decimal('0'),
    }
    
    # Données pour les filtres
    categories = CategorieDepense.objects.filter(actif=True)
    fournisseurs = Fournisseur.objects.filter(actif=True)
    
    context = {
        'page_obj': page_obj,
        'totaux': totaux,
        'categories': categories,
        'fournisseurs': fournisseurs,
        'statut_filtre': statut_filtre,
        'categorie_filtre': categorie_filtre,
        'fournisseur_filtre': fournisseur_filtre,
        'recherche': recherche,
    }
    
    return render(request, 'depenses/liste_depenses.html', context)

@login_required
def detail_depense(request, depense_id):
    """Détail d'une dépense"""
    qs = Depense.objects.select_related(
        'categorie', 'fournisseur', 'cree_par', 'valide_par'
    ).prefetch_related('pieces_justificatives', 'historique')
    if not user_is_admin(request.user):
        qs = qs.filter(cree_par__profil__ecole=user_school(request.user))
    depense = get_object_or_404(qs, id=depense_id)
    
    context = {
        'depense': depense,
    }
    
    return render(request, 'depenses/detail_depense.html', context)

@login_required
@can_add_expenses
def ajouter_depense(request):
    """Ajouter une nouvelle dépense"""
    if request.method == 'POST':
        form = DepenseForm(request.POST)
        if form.is_valid():
            depense = form.save(commit=False)
            depense.cree_par = request.user
            depense.save()
            
            # Créer l'historique
            HistoriqueDepense.objects.create(
                depense=depense,
                action='CREATION',
                description=f'Dépense créée: {depense.libelle}',
                nouveau_statut=depense.statut,
                utilisateur=request.user
            )
            
            messages.success(request, 'Dépense ajoutée avec succès.')
            return redirect('depenses:detail_depense', depense_id=depense.id)
    else:
        form = DepenseForm()
    
    context = {
        'form': form,
        'title': 'Ajouter une dépense',
    }
    
    return render(request, 'depenses/form_depense.html', context)

@login_required
@can_modify_expenses
def modifier_depense(request, depense_id):
    """Modifier une dépense existante"""
    qs = Depense.objects.all()
    if not user_is_admin(request.user):
        qs = qs.filter(cree_par__profil__ecole=user_school(request.user))
    depense = get_object_or_404(qs, id=depense_id)
    
    # Vérifier que la dépense peut être modifiée
    if depense.statut in ['PAYEE', 'ANNULEE']:
        messages.error(request, 'Cette dépense ne peut plus être modifiée.')
        return redirect('depenses:detail_depense', depense_id=depense.id)
    
    if request.method == 'POST':
        form = DepenseForm(request.POST, instance=depense)
        if form.is_valid():
            ancien_statut = depense.statut
            depense = form.save()
            
            # Créer l'historique
            HistoriqueDepense.objects.create(
                depense=depense,
                action='MODIFICATION',
                description=f'Dépense modifiée: {depense.libelle}',
                ancien_statut=ancien_statut,
                nouveau_statut=depense.statut,
                utilisateur=request.user
            )
            
            messages.success(request, 'Dépense modifiée avec succès.')
            return redirect('depenses:detail_depense', depense_id=depense.id)
    else:
        form = DepenseForm(instance=depense)
    
    context = {
        'form': form,
        'depense': depense,
        'title': 'Modifier la dépense',
    }
    
    return render(request, 'depenses/form_depense.html', context)

@login_required
@can_validate_expenses
def valider_depense(request, depense_id):
    """Valider une dépense"""
    if request.method == 'POST':
        qs = Depense.objects.all()
        if not user_is_admin(request.user):
            qs = qs.filter(cree_par__profil__ecole=user_school(request.user))
        depense = get_object_or_404(qs, id=depense_id)
        
        if depense.statut != 'EN_ATTENTE':
            messages.error(request, 'Seules les dépenses en attente peuvent être validées.')
        else:
            ancien_statut = depense.statut
            depense.statut = 'VALIDEE'
            depense.valide_par = request.user
            depense.date_validation = timezone.now()
            depense.save()
            
            # Créer l'historique
            HistoriqueDepense.objects.create(
                depense=depense,
                action='VALIDATION',
                description=f'Dépense validée: {depense.libelle}',
                ancien_statut=ancien_statut,
                nouveau_statut=depense.statut,
                utilisateur=request.user
            )
            
            messages.success(request, 'Dépense validée avec succès.')
    
    return redirect('depenses:detail_depense', depense_id=depense_id)

@login_required
def marquer_payee(request, depense_id):
    """Marquer une dépense comme payée"""
    if request.method == 'POST':
        qs = Depense.objects.all()
        if not user_is_admin(request.user):
            qs = qs.filter(cree_par__profil__ecole=user_school(request.user))
        depense = get_object_or_404(qs, id=depense_id)
        
        if depense.statut != 'VALIDEE':
            messages.error(request, 'Seules les dépenses validées peuvent être marquées comme payées.')
        else:
            ancien_statut = depense.statut
            depense.statut = 'PAYEE'
            depense.date_paiement = timezone.now().date()
            depense.save()
            
            # Créer l'historique
            HistoriqueDepense.objects.create(
                depense=depense,
                action='PAIEMENT',
                description=f'Dépense payée: {depense.libelle}',
                ancien_statut=ancien_statut,
                nouveau_statut=depense.statut,
                utilisateur=request.user
            )
            
            messages.success(request, 'Dépense marquée comme payée.')
    
    return redirect('depenses:detail_depense', depense_id=depense_id)

@login_required
def gestion_categories(request):
    """Gestion des catégories de dépenses: liste, filtres, création (AJAX)."""
    # Création par POST (AJAX)
    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip().upper()
        nom = (request.POST.get('nom') or '').strip()
        description = (request.POST.get('description') or '').strip()
        actif = request.POST.get('actif') in ['on', 'true', '1']
        budget_prevu = request.POST.get('budget_prevu')

        if not code or not nom:
            return JsonResponse({'success': False, 'error': "Code et Nom sont requis."}, status=400)
        if CategorieDepense.objects.filter(code=code).exists():
            return JsonResponse({'success': False, 'error': "Ce code existe déjà."}, status=400)

        categorie = CategorieDepense.objects.create(
            code=code, nom=nom, description=description or None, actif=actif
        )

        # Budget optionnel
        try:
            if budget_prevu not in [None, '']:
                montant = Decimal(budget_prevu)
                if montant > 0:
                    from django.utils import timezone as _tz
                    BudgetAnnuel.objects.create(
                        annee=_tz.now().year,
                        categorie=categorie,
                        budget_prevu=montant,
                        cree_par=request.user,
                    )
        except Exception:
            # On ignore les erreurs de budget pour ne pas bloquer la création
            pass

        return JsonResponse({'success': True})

    # GET: liste + filtres + pagination + stats
    categories = CategorieDepense.objects.all()

    search = (request.GET.get('search') or '').strip()
    if search:
        categories = categories.filter(Q(nom__icontains=search) | Q(code__icontains=search))

    actif_param = request.GET.get('actif')
    if actif_param in ['0', '1']:
        categories = categories.filter(actif=(actif_param == '1'))

    categories = categories.order_by('nom')

    paginator = Paginator(categories, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    total_categories = CategorieDepense.objects.count()
    categories_actives = CategorieDepense.objects.filter(actif=True).count()
    depenses_associees = Depense.objects.count()
    from django.db.models import Sum as _Sum
    budget_total = BudgetAnnuel.objects.aggregate(total=_Sum('budget_prevu'))['total'] or Decimal('0')

    context = {
        'categories': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'stats': {
            'total_categories': total_categories,
            'categories_actives': categories_actives,
            'depenses_associees': depenses_associees,
            'budget_total': budget_total,
        },
    }
    return render(request, 'depenses/gestion_categories.html', context)

@login_required
def gestion_fournisseurs(request):
    """Gestion des fournisseurs: liste, filtres, création (AJAX)."""
    # Création par POST (AJAX)
    if request.method == 'POST':
        nom = (request.POST.get('nom') or '').strip()
        type_fournisseur = (request.POST.get('type_fournisseur') or '').strip()
        adresse = (request.POST.get('adresse') or '').strip()
        telephone = (request.POST.get('telephone') or '').strip()
        email = (request.POST.get('email') or '').strip()
        actif = request.POST.get('actif') in ['on', 'true', '1']

        if not nom or not type_fournisseur:
            return JsonResponse({'success': False, 'error': "Nom et Type sont requis."}, status=400)

        fournisseur = Fournisseur.objects.create(
            nom=nom,
            type_fournisseur=type_fournisseur,
            adresse=adresse or '',
            telephone=telephone or '',
            email=email or None,
            actif=actif,
        )

        return JsonResponse({'success': True})

    # GET: liste + filtres + pagination + stats
    fournisseurs = Fournisseur.objects.all()

    search = (request.GET.get('search') or '').strip()
    if search:
        fournisseurs = fournisseurs.filter(nom__icontains=search)

    type_filtre = request.GET.get('type_fournisseur')
    if type_filtre:
        fournisseurs = fournisseurs.filter(type_fournisseur=type_filtre)

    actif_param = request.GET.get('actif')
    if actif_param in ['0', '1']:
        fournisseurs = fournisseurs.filter(actif=(actif_param == '1'))

    fournisseurs = fournisseurs.order_by('nom')

    paginator = Paginator(fournisseurs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    total_fournisseurs = Fournisseur.objects.count()
    fournisseurs_actifs = Fournisseur.objects.filter(actif=True).count()
    entreprises = Fournisseur.objects.filter(type_fournisseur='ENTREPRISE').count()
    particuliers = Fournisseur.objects.filter(type_fournisseur='PARTICULIER').count()

    context = {
        'fournisseurs': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'stats': {
            'total_fournisseurs': total_fournisseurs,
            'fournisseurs_actifs': fournisseurs_actifs,
            'entreprises': entreprises,
            'particuliers': particuliers,
        },
    }
    return render(request, 'depenses/gestion_fournisseurs.html', context)

@login_required
def activer_categorie(request, categorie_id):
    categorie = get_object_or_404(CategorieDepense, id=categorie_id)
    categorie.actif = True
    categorie.save(update_fields=['actif'])
    messages.success(request, 'Catégorie activée.')
    return redirect('depenses:gestion_categories')

@login_required
def desactiver_categorie(request, categorie_id):
    categorie = get_object_or_404(CategorieDepense, id=categorie_id)
    categorie.actif = False
    categorie.save(update_fields=['actif'])
    messages.success(request, 'Catégorie désactivée.')
    return redirect('depenses:gestion_categories')

@login_required
def activer_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    fournisseur.actif = True
    fournisseur.save(update_fields=['actif'])
    messages.success(request, 'Fournisseur activé.')
    return redirect('depenses:gestion_fournisseurs')

@login_required
def desactiver_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    fournisseur.actif = False
    fournisseur.save(update_fields=['actif'])
    messages.success(request, 'Fournisseur désactivé.')
    return redirect('depenses:gestion_fournisseurs')
