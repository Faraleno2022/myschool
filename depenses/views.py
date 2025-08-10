from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
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
    """Gestion des catégories de dépenses"""
    categories = CategorieDepense.objects.annotate(
        nb_depenses=Count('depenses')
    ).order_by('nom')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'depenses/gestion_categories.html', context)

@login_required
def gestion_fournisseurs(request):
    """Gestion des fournisseurs"""
    fournisseurs = Fournisseur.objects.annotate(
        nb_depenses=Count('depenses')
    ).order_by('nom')
    
    context = {
        'fournisseurs': fournisseurs,
    }
    
    return render(request, 'depenses/gestion_fournisseurs.html', context)
