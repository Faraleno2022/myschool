from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal
from datetime import date, datetime
import os

from .models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction
from eleves.models import Eleve, GrilleTarifaire, Classe
from .forms import PaiementForm, EcheancierForm, RechercheForm
from utilisateurs.utils import user_is_admin, filter_by_user_school, user_school
from rapports.utils import _draw_header_and_watermark

# ReportLab for PDF exports (used by tranches-par-classe)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

# --- Helpers ---
def _annee_vers_dates(annee_scolaire):
    """Retourne (annee_debut, annee_fin) à partir de '2024-2025'."""
    try:
        parts = annee_scolaire.split('-')
        an_deb = int(parts[0])
        an_fin = int(parts[1])
        return an_deb, an_fin
    except Exception:
        # Fallback: utilise année courante
        y = date.today().year
        # si on est après septembre, année scolaire y-(y+1), sinon (y-1)-y
        if date.today().month >= 9:
            return y, y + 1
        return y - 1, y

def _dates_echeances_par_ecole(nom_ecole, annee_scolaire, date_inscription=None):
    """Calcule les dates d'échéance par conventions fournies.
    - Sonfonia: À l’inscription (tranche 1), 05-10 Janvier (tranche 2 -> on met 10/01), 01-06 Avril (tranche 3 -> on met 06/04)
    - Somayah: À l’inscription (tranche 1), Début janvier (tranche 2 -> 05/01), Début mars (tranche 3 -> 05/03)
    """
    an_deb, an_fin = _annee_vers_dates(annee_scolaire)

    # Inscription: utilise la date d'inscription élève si disponible, sinon 30/09 de l'année_debut
    date_insc = date_inscription or date(an_deb, 9, 30)

    nom = (nom_ecole or '').strip().lower()
    if 'somayah' in nom:
        d1 = date_insc
        d2 = date(an_fin, 1, 5)   # début janvier
        d3 = date(an_fin, 3, 5)   # début mars
    else:
        # défaut: Sonfonia
        d1 = date_insc
        d2 = date(an_fin, 1, 10)  # 05 au 10 janvier -> on prend le 10
        d3 = date(an_fin, 4, 6)   # 01 au 06 avril -> on prend le 6

    # Échéance d'inscription: même jour que d1
    return d1, d2, d3

def _map_type_to_tranche(type_paiement_nom: str):
    """Retourne l'identifiant de tranche pour un nom de type ('Inscription', 'Tranche 1', 'Tranche 2', 'Tranche 3')."""
    nom = (type_paiement_nom or '').strip().lower()
    if 'inscription' in nom:
        return 'inscription'
    if 'tranche' in nom:
        if '1' in nom:
            return 't1'
        if '2' in nom:
            return 't2'
        if '3' in nom:
            return 't3'
    return None

def _allocate_payment_to_echeancier(echeancier: EcheancierPaiement, montant: Decimal, date_pay: date, cible: str | None):
    """Distribue le montant sur les lignes de l'échéancier dans l'ordre.
    Renvoie un dict: {warnings: [..], info: [..]}"""
    warnings = []
    infos = []

    # Snapshot avant paiement
    total_paye_avant = echeancier.total_paye
    solde_avant = echeancier.solde_restant

    # Définition des tranches dans l'ordre à payer
    ordre = ['inscription', 't1', 't2', 't3']
    if cible in ordre:
        # Si un type est ciblé, on commence par celui-ci puis on continue
        ordre = [cible] + [x for x in ordre if x != cible]

    def tranche_data(key):
        if key == 'inscription':
            return (
                'frais_inscription_du', 'frais_inscription_paye', 'date_echeance_inscription', 'Inscription'
            )
        if key == 't1':
            return ('tranche_1_due', 'tranche_1_payee', 'date_echeance_tranche_1', 'Tranche 1')
        if key == 't2':
            return ('tranche_2_due', 'tranche_2_payee', 'date_echeance_tranche_2', 'Tranche 2')
        if key == 't3':
            return ('tranche_3_due', 'tranche_3_payee', 'date_echeance_tranche_3', 'Tranche 3')
        raise ValueError('Tranche inconnue')

    restant = Decimal(montant)
    for key in ordre:
        if restant <= 0:
            break
        due_field, paid_field, due_date_field, label = tranche_data(key)
        due = getattr(echeancier, due_field)
        paid = getattr(echeancier, paid_field)
        to_pay = max(Decimal('0'), due - paid)
        if to_pay <= 0:
            continue

        # Retard ?
        due_date = getattr(echeancier, due_date_field)
        if date_pay > due_date:
            delta = (date_pay - due_date).days
            warnings.append(f"Retard sur {label}: {delta} jour(s) après l'échéance ({due_date.strftime('%d/%m/%Y')}).")

        pay_now = min(restant, to_pay)
        if pay_now < restant and cible in ['inscription', 't1', 't2', 't3'] and key == cible and restant > to_pay:
            # L'utilisateur a payé plus que la tranche ciblée
            depasse = int(restant - to_pay)
            if depasse > 0:
                warnings.append(f"Le montant payé dépasse {label} de {depasse:,.0f} GNF.")

        setattr(echeancier, paid_field, paid + pay_now)
        restant -= pay_now

    # Mettre à jour le statut
    if echeancier.solde_restant <= 0:
        echeancier.statut = 'PAYE_COMPLET'
    else:
        # Vérifier s'il existe du retard résiduel (au moins une tranche échue non soldée)
        now = date_pay
        en_retard = (
            (now > echeancier.date_echeance_inscription and echeancier.frais_inscription_paye < echeancier.frais_inscription_du) or
            (now > echeancier.date_echeance_tranche_1 and echeancier.tranche_1_payee < echeancier.tranche_1_due) or
            (now > echeancier.date_echeance_tranche_2 and echeancier.tranche_2_payee < echeancier.tranche_2_due) or
            (now > echeancier.date_echeance_tranche_3 and echeancier.tranche_3_payee < echeancier.tranche_3_due)
        )
        echeancier.statut = 'EN_RETARD' if en_retard else 'PAYE_PARTIEL'

    # Paiement de toutes les tranches en une fois ?
    if total_paye_avant == 0 and echeancier.solde_restant == 0 and montant >= solde_avant:
        infos.append("Toutes les tranches ont été réglées en une seule fois. Merci !")

    return {'warnings': warnings, 'info': infos}

@login_required
def tableau_bord_paiements(request):
    """Tableau de bord principal des paiements"""
    # Base querysets filtrés par école si non-admin
    paiements_qs = Paiement.objects.all()
    echeanciers_qs = EcheancierPaiement.objects.all()
    if not user_is_admin(request.user):
        paiements_qs = filter_by_user_school(paiements_qs, request.user, 'eleve__classe__ecole')
        echeanciers_qs = filter_by_user_school(echeanciers_qs, request.user, 'eleve__classe__ecole')

    # Statistiques générales
    stats = {
        'total_paiements_mois': paiements_qs.filter(
            date_paiement__month=timezone.now().month,
            date_paiement__year=timezone.now().year,
            statut='VALIDE'
        ).aggregate(total=Sum('montant'))['total'] or 0,
        
        'nombre_paiements_mois': paiements_qs.filter(
            date_paiement__month=timezone.now().month,
            date_paiement__year=timezone.now().year,
            statut='VALIDE'
        ).count(),
        
        'eleves_en_retard': echeanciers_qs.filter(
            statut='EN_RETARD'
        ).count(),
        
        'paiements_en_attente': paiements_qs.filter(
            statut='EN_ATTENTE'
        ).count(),
    }
    
    # Paiements récents
    paiements_recents = paiements_qs.select_related(
        'eleve', 'type_paiement', 'mode_paiement'
    ).order_by('-date_paiement')[:10]
    
    # Élèves en retard de paiement
    eleves_en_retard = echeanciers_qs.filter(
        statut='EN_RETARD'
    ).select_related('eleve', 'eleve__classe')[:10]
    
    context = {
        'stats': stats,
        'paiements_recents': paiements_recents,
        'eleves_en_retard': eleves_en_retard,
        'titre_page': 'Tableau de Bord - Paiements',
    }
    
    return render(request, 'paiements/tableau_bord.html', context)

@login_required
def liste_paiements(request):
    """Liste de tous les paiements avec une zone de recherche multi-critères (classe, école, nom, prénoms, type, mode, n° reçu, matricule, statut)."""
    paiements = Paiement.objects.select_related(
        'eleve', 'type_paiement', 'mode_paiement', 'valide_par', 'eleve__classe', 'eleve__classe__ecole'
    ).order_by('-date_paiement')

    # Filtrage par école pour non-admin
    if not user_is_admin(request.user):
        paiements = filter_by_user_school(paiements, request.user, 'eleve__classe__ecole')

    q = (request.GET.get('q') or '').strip()
    if q:
        q_lower = q.lower()
        filtres = (
            Q(eleve__nom__icontains=q) |
            Q(eleve__prenom__icontains=q) |
            Q(eleve__matricule__icontains=q) |
            Q(numero_recu__icontains=q) |
            Q(eleve__classe__nom__icontains=q) |
            Q(eleve__classe__ecole__nom__icontains=q) |
            Q(type_paiement__nom__icontains=q) |
            Q(mode_paiement__nom__icontains=q)
        )
        # Mapping simple sur le statut si le texte correspond
        statut_map = {
            'valide': 'VALIDE', 'validé': 'VALIDE', 'ok': 'VALIDE',
            'attente': 'EN_ATTENTE', 'en attente': 'EN_ATTENTE', 'pending': 'EN_ATTENTE',
            'rejete': 'REJETE', 'rejeté': 'REJETE', 'rejete': 'REJETE',
            'annule': 'ANNULE', 'annulé': 'ANNULE', 'annulee': 'ANNULE', 'annulée': 'ANNULE'
        }
        for key, code in statut_map.items():
            if key in q_lower:
                filtres = filtres | Q(statut=code)
        paiements = paiements.filter(filtres)
    
    # Calcul des totaux dynamiques (basés sur les filtres)
    from django.db.models import Sum, Count
    from datetime import datetime
    
    # Totaux généraux (sur les paiements filtrés)
    totaux = {
        'total_paiements': paiements.count(),
        'montant_total': paiements.aggregate(total=Sum('montant'))['total'] or 0,
        'total_en_attente': paiements.filter(statut='EN_ATTENTE').count(),
        'montant_en_attente': paiements.filter(statut='EN_ATTENTE').aggregate(total=Sum('montant'))['total'] or 0,
    }
    
    # Totaux ce mois (sur les paiements filtrés)
    current_month = datetime.now().month
    current_year = datetime.now().year
    paiements_ce_mois = paiements.filter(
        date_paiement__month=current_month,
        date_paiement__year=current_year
    )
    
    totaux.update({
        'total_ce_mois': paiements_ce_mois.count(),
        'montant_ce_mois': paiements_ce_mois.aggregate(total=Sum('montant'))['total'] or 0,
    })
    
    # Pagination
    paginator = Paginator(paiements, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'totaux': totaux,
        'titre_page': 'Liste des Paiements',
        'q': q,
    }
    
    # Si requête AJAX, renvoyer uniquement le fragment (totaux + tableau + pagination)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'paiements/_paiements_resultats.html', context)

    return render(request, 'paiements/liste_paiements.html', context)

@login_required
def detail_paiement(request, paiement_id):
    """Détail d'un paiement"""
    qs = Paiement.objects.select_related(
        'eleve', 'type_paiement', 'mode_paiement', 'valide_par', 'cree_par'
    ).prefetch_related('remises__remise')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')
    paiement = get_object_or_404(qs, id=paiement_id)
    
    context = {
        'paiement': paiement,
        'titre_page': f'Paiement #{paiement.numero_recu}',
    }
    
    return render(request, 'paiements/detail_paiement.html', context)

@login_required
def ajouter_paiement(request, eleve_id=None):
    """Ajouter un nouveau paiement"""
    eleve = None
    if eleve_id:
        eleves_qs = Eleve.objects.select_related('classe', 'classe__ecole')
        if not user_is_admin(request.user):
            eleves_qs = filter_by_user_school(eleves_qs, request.user, 'classe__ecole')
        eleve = get_object_or_404(eleves_qs, id=eleve_id)
    
    if request.method == 'POST':
        form = PaiementForm(request.POST)
        # Restreindre le champ élève aux élèves de l'école de l'utilisateur (si non-admin)
        if 'eleve' in form.fields and not user_is_admin(request.user):
            form.fields['eleve'].queryset = filter_by_user_school(
                Eleve.objects.select_related('classe', 'classe__ecole'), request.user, 'classe__ecole'
            )
        if form.is_valid():
            # Contrôle: bloquer si le total annuel déjà atteint
            eleve_cible = form.cleaned_data.get('eleve')
            try:
                echeancier = eleve_cible.echeancier
                total_a_payer = (
                    (echeancier.frais_inscription_du or Decimal('0')) +
                    (echeancier.tranche_1_due or Decimal('0')) +
                    (echeancier.tranche_2_due or Decimal('0')) +
                    (echeancier.tranche_3_due or Decimal('0'))
                )
                total_paye = (
                    (echeancier.frais_inscription_paye or Decimal('0')) +
                    (echeancier.tranche_1_payee or Decimal('0')) +
                    (echeancier.tranche_2_payee or Decimal('0')) +
                    (echeancier.tranche_3_payee or Decimal('0'))
                )
                solde = total_a_payer - total_paye
                if solde <= 0:
                    messages.warning(request, "Le montant annuel a déjà été entièrement réglé pour cet élève. Aucun nouveau paiement ne peut être enregistré.")
                    # Réafficher le formulaire sans enregistrer
                    context = {
                        'form': form,
                        'eleve': eleve_cible if eleve is None else eleve,
                        'titre_page': 'Nouveau Paiement',
                        'action': 'Ajouter'
                    }
                    return render(request, 'paiements/form_paiement.html', context)
                # Empêcher un paiement supérieur au solde restant
                montant_saisi = form.cleaned_data.get('montant') or Decimal('0')
                if montant_saisi > solde:
                    form.add_error('montant', f"Le montant saisi dépasse le reste à payer ({int(solde):,} GNF).".replace(',', ' '))
                    messages.warning(request, f"Montant supérieur au reste à payer. Reste: {int(solde):,} GNF.".replace(',', ' '))
                    context = {
                        'form': form,
                        'eleve': eleve_cible if eleve is None else eleve,
                        'titre_page': 'Nouveau Paiement',
                        'action': 'Ajouter'
                    }
                    return render(request, 'paiements/form_paiement.html', context)
            except EcheancierPaiement.DoesNotExist:
                # Pas d'échéancier -> pas de blocage, on laissera enregistrer et guidera après
                pass

            paiement = form.save(commit=False)
            paiement.cree_par = request.user

            # Générer le numéro de reçu automatiquement
            dernier_numero = Paiement.objects.filter(
                date_paiement__year=timezone.now().year
            ).count() + 1
            paiement.numero_recu = f"REC{timezone.now().year}{dernier_numero:04d}"

            paiement.save()

            # Ne pas impacter l'échéancier tant que le paiement n'est pas validé
            try:
                _ = paiement.eleve.echeancier
                messages.success(request, f"Paiement enregistré avec succès (en attente de validation). Reçu #{paiement.numero_recu}")
                return redirect('paiements:detail_paiement', paiement_id=paiement.id)
            except EcheancierPaiement.DoesNotExist:
                # Pas d'échéancier: guider l'utilisateur pour en créer un immédiatement
                messages.success(request, f"Paiement enregistré avec succès (en attente de validation). Reçu #{paiement.numero_recu}")
                messages.info(request, "Aucun échéancier n'existe pour cet élève. Veuillez le créer maintenant pour suivre les tranches.")
                return redirect('paiements:creer_echeancier', eleve_id=paiement.eleve.id)
    else:
        form = PaiementForm()
        # Restreindre le champ élève aux élèves de l'école de l'utilisateur (si non-admin)
        if 'eleve' in form.fields and not user_is_admin(request.user):
            form.fields['eleve'].queryset = filter_by_user_school(
                Eleve.objects.select_related('classe', 'classe__ecole'), request.user, 'classe__ecole'
            )
        if eleve:
            form.fields['eleve'].initial = eleve
        # Ne pas forcer la date du jour par défaut: laisser le formulaire gérer la valeur (initiale éventuelle ou vide)
    
    context = {
        'form': form,
        'eleve': eleve,
        'titre_page': 'Nouveau Paiement',
        'action': 'Ajouter'
    }
    
    return render(request, 'paiements/form_paiement.html', context)

@login_required
def echeancier_eleve(request, eleve_id):
    """Afficher l'échéancier d'un élève"""
    eleves_qs = Eleve.objects.select_related('classe', 'classe__ecole')
    if not user_is_admin(request.user):
        eleves_qs = filter_by_user_school(eleves_qs, request.user, 'classe__ecole')
    eleve = get_object_or_404(eleves_qs, id=eleve_id)
    
    try:
        echeancier = eleve.echeancier
    except EcheancierPaiement.DoesNotExist:
        # Créer un échéancier si il n'existe pas
        echeancier = None
    
    # Historique des paiements de l'élève
    paiements = eleve.paiements.select_related(
        'type_paiement', 'mode_paiement'
    ).order_by('-date_paiement')
    
    context = {
        'eleve': eleve,
        'echeancier': echeancier,
        'paiements': paiements,
        'titre_page': f'Échéancier - {eleve.prenom} {eleve.nom}',
    }
    
    return render(request, 'paiements/echeancier_eleve.html', context)

@login_required
def creer_echeancier(request, eleve_id):
    """Créer un échéancier pour un élève"""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    
    # Vérifier si un échéancier existe déjà
    if hasattr(eleve, 'echeancier'):
        messages.warning(request, "Un échéancier existe déjà pour cet élève.")
        return redirect('paiements:echeancier_eleve', eleve_id=eleve.id)
    
    if request.method == 'POST':
        # Recalculer et injecter côté serveur pour garantir les valeurs, même si les inputs sont readonly
        data = request.POST.copy()
        # Année scolaire depuis la classe
        if getattr(eleve.classe, 'annee_scolaire', None):
            data['annee_scolaire'] = eleve.classe.annee_scolaire

        grille = GrilleTarifaire.objects.filter(
            ecole=eleve.classe.ecole,
            niveau=eleve.classe.niveau,
            annee_scolaire=eleve.classe.annee_scolaire,
        ).first()
        if grille:
            # Montants depuis la grille
            data['frais_inscription_du'] = str(grille.frais_inscription)
            data['tranche_1_due'] = str(grille.tranche_1)
            data['tranche_2_due'] = str(grille.tranche_2)
            data['tranche_3_due'] = str(grille.tranche_3)

            # Dates selon l'école
            d1, d2, d3 = _dates_echeances_par_ecole(
                nom_ecole=eleve.classe.ecole.nom,
                annee_scolaire=eleve.classe.annee_scolaire,
                date_inscription=getattr(eleve, 'date_inscription', None),
            )
            data['date_echeance_inscription'] = d1.isoformat()
            data['date_echeance_tranche_1'] = d1.isoformat()
            data['date_echeance_tranche_2'] = d2.isoformat()
            data['date_echeance_tranche_3'] = d3.isoformat()
        else:
            messages.warning(request, "Aucune grille tarifaire trouvée pour cette classe et cette année. Merci de la créer d'abord.")

        form = EcheancierForm(data)
        if form.is_valid():
            echeancier = form.save(commit=False)
            echeancier.eleve = eleve
            echeancier.cree_par = request.user
            echeancier.save()

            messages.success(request, f"Échéancier créé avec succès pour {eleve.prenom} {eleve.nom}.")
            return redirect('paiements:echeancier_eleve', eleve_id=eleve.id)
    else:
        # Pré-remplir avec les données de la grille tarifaire ET les dates par défaut
        form = EcheancierForm()
        # Année scolaire forcée depuis la classe de l'élève
        if getattr(eleve.classe, 'annee_scolaire', None):
            form.fields['annee_scolaire'].initial = eleve.classe.annee_scolaire
        grille = GrilleTarifaire.objects.filter(
            ecole=eleve.classe.ecole,
            niveau=eleve.classe.niveau,
            annee_scolaire=eleve.classe.annee_scolaire,
        ).first()
        if grille:
            # Montants
            form.fields['frais_inscription_du'].initial = grille.frais_inscription
            form.fields['tranche_1_due'].initial = grille.tranche_1
            form.fields['tranche_2_due'].initial = grille.tranche_2
            form.fields['tranche_3_due'].initial = grille.tranche_3

            # Dates selon école et année scolaire
            d1, d2, d3 = _dates_echeances_par_ecole(
                nom_ecole=eleve.classe.ecole.nom,
                annee_scolaire=eleve.classe.annee_scolaire,
                date_inscription=getattr(eleve, 'date_inscription', None),
            )
            form.fields['date_echeance_inscription'].initial = d1
            form.fields['date_echeance_tranche_1'].initial = d1  # Tranche 1 à l'inscription
            form.fields['date_echeance_tranche_2'].initial = d2
            form.fields['date_echeance_tranche_3'].initial = d3

            # Forcer l'affichage des dates (inputs type=date + readonly) en définissant la valeur ISO
            form.fields['date_echeance_inscription'].widget.attrs['value'] = d1.isoformat()
            form.fields['date_echeance_tranche_1'].widget.attrs['value'] = d1.isoformat()
            form.fields['date_echeance_tranche_2'].widget.attrs['value'] = d2.isoformat()
            form.fields['date_echeance_tranche_3'].widget.attrs['value'] = d3.isoformat()
            # Et donner un fallback via data-iso pour le JS
            form.fields['date_echeance_inscription'].widget.attrs['data-iso'] = d1.isoformat()
            form.fields['date_echeance_tranche_1'].widget.attrs['data-iso'] = d1.isoformat()
            form.fields['date_echeance_tranche_2'].widget.attrs['data-iso'] = d2.isoformat()
            form.fields['date_echeance_tranche_3'].widget.attrs['data-iso'] = d3.isoformat()

            # Rendre lecture seule à l'affichage (tout en envoyant les valeurs au POST)
            readonly_fields = [
                'annee_scolaire',
                'frais_inscription_du', 'tranche_1_due', 'tranche_2_due', 'tranche_3_due',
                'date_echeance_inscription', 'date_echeance_tranche_1', 'date_echeance_tranche_2', 'date_echeance_tranche_3',
            ]
            for fname in readonly_fields:
                try:
                    form.fields[fname].widget.attrs['readonly'] = 'readonly'
                except Exception:
                    pass
        else:
            messages.warning(request, "Aucune grille tarifaire trouvée pour cette classe et cette année. Merci de la créer d'abord.")
    
    context = {
        'form': form,
        'eleve': eleve,
        'grille': grille if 'grille' in locals() else None,
        'titre_page': f'Créer Échéancier - {eleve.prenom} {eleve.nom}',
        'action': 'Créer'
    }
    
    return render(request, 'paiements/form_echeancier.html', context)

@login_required
def valider_paiement(request, paiement_id):
    """Valider un paiement en attente"""
    if request.method == 'POST':
        qs = Paiement.objects.all()
        if not user_is_admin(request.user):
            qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')
        paiement = get_object_or_404(qs, id=paiement_id)
        
        if paiement.statut == 'EN_ATTENTE':
            paiement.statut = 'VALIDE'
            paiement.valide_par = request.user
            paiement.date_validation = timezone.now()
            paiement.save()
            
            # Impacter l'échéancier à la validation
            try:
                echeancier = paiement.eleve.echeancier
                cible = _map_type_to_tranche(getattr(paiement.type_paiement, 'nom', ''))
                feedback = _allocate_payment_to_echeancier(
                    echeancier=echeancier,
                    montant=paiement.montant,
                    date_pay=paiement.date_paiement,
                    cible=cible,
                )
                echeancier.save()

                for w in feedback['warnings']:
                    messages.warning(request, w)
                for info in feedback['info']:
                    messages.info(request, info)
            except EcheancierPaiement.DoesNotExist:
                messages.info(request, "Aucun échéancier n'existe pour cet élève. Veuillez le créer pour refléter ce paiement dans les tranches.")

            messages.success(request, f"Paiement #{paiement.numero_recu} validé avec succès.")
        else:
            messages.error(request, "Ce paiement ne peut pas être validé.")
    
    return redirect('paiements:detail_paiement', paiement_id=paiement_id)

@login_required
def generer_recu_pdf(request, paiement_id):
    """Générer un reçu PDF pour un paiement"""
    qs = Paiement.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole', 'type_paiement', 'mode_paiement')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')
    paiement = get_object_or_404(qs, id=paiement_id)
    
    # Génération du PDF avec ReportLab si disponible
    try:
        import io
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from django.utils.formats import number_format
        from django.utils.timezone import localtime
        from django.contrib.staticfiles import finders
    except Exception:
        messages.error(request, "La génération de PDF nécessite la bibliothèque ReportLab. Veuillez l'installer (pip install reportlab).")
        return redirect('paiements:detail_paiement', paiement_id=paiement.id)

    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    # Marges
    margin_x = 20 * mm
    margin_y = 20 * mm

    # Filigrane (logo géant ~500%)
    try:
        logo_path = finders.find('logos/logo.png')
    except Exception:
        logo_path = None

    if logo_path:
        c.saveState()
        try:
            wm_width = width * 1.5  # ~150% de la largeur page -> effet 500%
            wm_height = wm_width
            wm_x = (width - wm_width) / 2
            wm_y = (height - wm_height) / 2
            try:
                c.setFillAlpha(0.08)
            except Exception:
                pass
            c.translate(width / 2.0, height / 2.0)
            c.rotate(30)
            c.translate(-width / 2.0, -height / 2.0)
            c.drawImage(logo_path, wm_x, wm_y, width=wm_width, height=wm_height, preserveAspectRatio=True, mask='auto')
        finally:
            c.restoreState()

    # En-tête avec logo + titre
    c.saveState()
    try:
        if logo_path:
            c.drawImage(logo_path, margin_x, height - margin_y - 30, width=60, height=30, preserveAspectRatio=True, mask='auto')
        c.setFillColor(colors.HexColor('#0056b3'))
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin_x + 70, height - margin_y - 10, "École Moderne HADJA KANFING DIANÉ")
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_x + 70, height - margin_y - 28, f"Reçu de paiement #{paiement.numero_recu}")
        # Ligne de séparation
        c.setStrokeColor(colors.HexColor('#0056b3'))
        c.setLineWidth(1)
        c.line(margin_x, height - margin_y - 38, width - margin_x, height - margin_y - 38)
    finally:
        c.restoreState()

    # Photo de l'élève (en haut à droite, sous l'entête)
    try:
        if getattr(paiement.eleve, 'photo', None) and paiement.eleve.photo.name:
            eleve_photo_path = paiement.eleve.photo.path  # chemin fichier local
            photo_box = 28 * mm  # taille carrée ~28mm
            photo_x = width - margin_x - photo_box
            photo_y = height - margin_y - 38 - photo_box - 6  # sous la ligne d'entête avec petit offset
            c.drawImage(
                eleve_photo_path,
                photo_x,
                photo_y,
                width=photo_box,
                height=photo_box,
                preserveAspectRatio=True,
                mask='auto'
            )
    except Exception:
        # Si l'image n'est pas disponible ou invalide, on ignore sans bloquer la génération du PDF
        pass

    # Informations élève et paiement
    y = height - margin_y - 60
    c.setFont("Helvetica", 11)

    def line(label, value):
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_x, y, f"{label} :")
        c.setFont("Helvetica", 11)
        c.drawString(margin_x + 140, y, str(value))
        y -= 16

    # Formatage
    montant_fmt = f"{int(paiement.montant):,}".replace(',', ' ')
    date_pay = localtime(paiement.date_validation).strftime('%d/%m/%Y %H:%M') if paiement.date_validation else paiement.date_paiement.strftime('%d/%m/%Y')

    line("Élève", f"{paiement.eleve.prenom} {paiement.eleve.nom} (Mat: {paiement.eleve.matricule})")
    line("Classe", f"{paiement.eleve.classe.nom} - {paiement.eleve.classe.ecole.nom}")
    line("Date de paiement", date_pay)
    line("Type de paiement", paiement.type_paiement.nom)
    line("Mode de paiement", paiement.mode_paiement.nom)
    line("Montant", f"{montant_fmt} GNF")
    line("Statut", paiement.get_statut_display())
    if paiement.reference_externe:
        line("Référence", paiement.reference_externe)

    # Observations
    if paiement.observations:
        y -= 6
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_x, y, "Observations :")
        y -= 14
        c.setFont("Helvetica", 10)
        text_obj = c.beginText(margin_x, y)
        text_obj.setLeading(14)
        for part in str(paiement.observations).split('\n'):
            text_obj.textLine(part)
        c.drawText(text_obj)
        y = text_obj.getY() - 8

    # Résumé Échéancier (totaux et tranches)
    try:
        echeancier = paiement.eleve.echeancier
        # Totaux
        total_a_payer = (
            (echeancier.frais_inscription_du or Decimal('0')) +
            (echeancier.tranche_1_due or Decimal('0')) +
            (echeancier.tranche_2_due or Decimal('0')) +
            (echeancier.tranche_3_due or Decimal('0'))
        )
        total_paye = echeancier.total_paye if hasattr(echeancier, 'total_paye') else (
            (echeancier.frais_inscription_paye or Decimal('0')) +
            (echeancier.tranche_1_payee or Decimal('0')) +
            (echeancier.tranche_2_payee or Decimal('0')) +
            (echeancier.tranche_3_payee or Decimal('0'))
        )
        reste = echeancier.solde_restant if hasattr(echeancier, 'solde_restant') else max(Decimal('0'), total_a_payer - total_paye)

        def fmt_money(d):
            return f"{int(d):,}".replace(',', ' ') + " GNF"

        y -= 10
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_x, y, "Résumé de l'échéancier")
        y -= 18
        c.setFont("Helvetica", 11)
        line("Total à payer", fmt_money(total_a_payer))
        line("Déjà payé", fmt_money(total_paye))
        line("Reste à payer", fmt_money(reste))

        # Détail par tranche
        y -= 4
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_x, y, "Détail des tranches :")
        y -= 16
        c.setFont("Helvetica", 10)
        detail = [
            ("Inscription", echeancier.frais_inscription_du or Decimal('0'), echeancier.frais_inscription_paye or Decimal('0')),
            ("Tranche 1", echeancier.tranche_1_due or Decimal('0'), echeancier.tranche_1_payee or Decimal('0')),
            ("Tranche 2", echeancier.tranche_2_due or Decimal('0'), echeancier.tranche_2_payee or Decimal('0')),
            ("Tranche 3", echeancier.tranche_3_due or Decimal('0'), echeancier.tranche_3_payee or Decimal('0')),
        ]
        for label, due, paid in detail:
            rest = max(Decimal('0'), due - paid)
            c.drawString(margin_x, y, f"{label} : dû {fmt_money(due)} | payé {fmt_money(paid)} | reste {fmt_money(rest)}")
            y -= 14
    except EcheancierPaiement.DoesNotExist:
        y -= 10
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(margin_x, y, "Aucun échéancier n'est associé à cet élève.")

    # Pied de page
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawString(margin_x, margin_y, "Ce reçu est généré automatiquement par le système de gestion scolaire.")

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f"inline; filename=recu_{paiement.numero_recu}.pdf"
    response.write(pdf)
    return response

@login_required
def export_tranches_par_classe_pdf(request):
    """Exporter en PDF la liste des élèves avec montants par tranches, total scolarité et reste à payer.
    Colonnes: Élève, Classe, Tranche 1 (payée), Tranche 2 (payée), Tranche 3 (payée), Scolarité annuelle (due), Reste scolarité.

    Filtres optionnels:
    - classe_id: ID de la classe (pour limiter à une classe)
    - annee_scolaire: chaîne "YYYY-YYYY" pour sélectionner l'échéancier correspondant
    """
    # Préparation du queryset des élèves + échéanciers
    eleves_qs = Eleve.objects.select_related('classe', 'classe__ecole')
    if not user_is_admin(request.user):
        eleves_qs = filter_by_user_school(eleves_qs, request.user, 'classe__ecole')

    classe_id = request.GET.get('classe_id')
    if classe_id:
        try:
            eleves_qs = eleves_qs.filter(classe_id=int(classe_id))
        except Exception:
            pass

    annee_scolaire = (request.GET.get('annee_scolaire') or '').strip()

    # Charger les échéanciers correspondants (si annee_scolaire fournie, on filtre dessus)
    echeanciers_map = {}
    echeanciers_qs = EcheancierPaiement.objects.select_related('eleve', 'eleve__classe')
    if not user_is_admin(request.user):
        echeanciers_qs = filter_by_user_school(echeanciers_qs, request.user, 'eleve__classe__ecole')
    if annee_scolaire:
        echeanciers_qs = echeanciers_qs.filter(annee_scolaire=annee_scolaire)
    for e in echeanciers_qs:
        echeanciers_map[e.eleve_id] = e

    # Génération du PDF (ReportLab - platypus) en paysage
    try:
        import io
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from django.contrib.staticfiles import finders
    except Exception:
        messages.error(request, "La génération de PDF nécessite la bibliothèque ReportLab. Veuillez l'installer (pip install reportlab).")
        return redirect('paiements:liste_paiements')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10, rightMargin=10, topMargin=16, bottomMargin=16,
    )

    styles = getSampleStyleSheet()
    styleN = ParagraphStyle('tiny', parent=styles['Normal'], fontSize=8, leading=9)
    styleH = ParagraphStyle('head', parent=styles['Heading2'], fontSize=12)

    elements = []

    # En-tête avec logo et titre via un tableau simple
    try:
        logo_path = finders.find('logos/logo.png')
    except Exception:
        logo_path = None

    title_text = "Paiements par tranches – par classe"
    if annee_scolaire:
        title_text += f" ({annee_scolaire})"

    # En-tête simple
    from reportlab.platypus import Image
    header_cells = []
    if logo_path:
        header_cells = [[Image(logo_path, width=40, height=20), Paragraph(title_text, styles['Title'])]]
        col_widths_header = [50, None]
    else:
        header_cells = [[Paragraph(title_text, styles['Title'])]]
        col_widths_header = [None]
    header_table = Table(header_cells, colWidths=col_widths_header)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(0, 4))

    # Préparer les données du tableau
    data = [[
        'Élève', 'Classe', 'Tranche 1', 'Tranche 2', 'Tranche 3', 'Scolarité annuelle', 'Reste scolarité'
    ]]

    # Tri: par école, puis par niveau de classe (ordre logique), puis par nom de classe et élève
    # On annote un ordre numérique pour les niveaux afin d'imposer: Garderie, Maternelle, Primaire 1..6, Collège 7..10, Lycée 11..12, Terminale
    from django.db.models import Case, When, IntegerField
    niveau_order = Case(
        When(classe__niveau='GARDERIE', then=0),
        When(classe__niveau='MATERNELLE', then=1),
        When(classe__niveau='PRIMAIRE_1', then=2),
        When(classe__niveau='PRIMAIRE_2', then=3),
        When(classe__niveau='PRIMAIRE_3', then=4),
        When(classe__niveau='PRIMAIRE_4', then=5),
        When(classe__niveau='PRIMAIRE_5', then=6),
        When(classe__niveau='PRIMAIRE_6', then=7),
        When(classe__niveau='COLLEGE_7', then=8),
        When(classe__niveau='COLLEGE_8', then=9),
        When(classe__niveau='COLLEGE_9', then=10),
        When(classe__niveau='COLLEGE_10', then=11),
        When(classe__niveau='LYCEE_11', then=12),
        When(classe__niveau='LYCEE_12', then=13),
        When(classe__niveau='TERMINALE', then=14),
        output_field=IntegerField()
    )
    eleves = eleves_qs.annotate(niv_order=niveau_order).order_by('classe__ecole__nom', 'niv_order', 'classe__nom', 'nom', 'prenom')

    for el in eleves:
        e = echeanciers_map.get(el.id)
        if not e:
            # Pas d'échéancier (ou pas pour l'année demandée) -> ignorer ou afficher 0
            t1_p = t2_p = t3_p = Decimal('0')
            t1_d = t2_d = t3_d = Decimal('0')
        else:
            t1_p = e.tranche_1_payee or Decimal('0')
            t2_p = e.tranche_2_payee or Decimal('0')
            t3_p = e.tranche_3_payee or Decimal('0')
            t1_d = e.tranche_1_due or Decimal('0')
            t2_d = e.tranche_2_due or Decimal('0')
            t3_d = e.tranche_3_due or Decimal('0')

        scolarite_due = t1_d + t2_d + t3_d
        paye_tranches = t1_p + t2_p + t3_p
        reste_scolarite = max(Decimal('0'), scolarite_due - paye_tranches)

        def fmt(d):
            return f"{int(d):,}".replace(',', ' ')

        data.append([
            Paragraph(f"{el.prenom} {el.nom}", styleN),
            Paragraph(f"{el.classe.nom}", styleN),
            fmt(t1_p),
            fmt(t2_p),
            fmt(t3_p),
            fmt(scolarite_due),
            fmt(reste_scolarite),
        ])

    # Largeurs approximatives pour tenir en paysage A4
    col_widths = [110, 70, 55, 55, 55, 70, 70]
    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f0ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#003366')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#003366')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.Color(0.98, 0.98, 0.98)]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))

    elements.append(table)

    # Filigrane via onPage callback
    def _on_page(canvas, doc_):
        if not logo_path:
            return
        width, height = landscape(A4)
        try:
            canvas.saveState()
            # Filigrane légèrement réduit
            wm_w = width * 0.75
            wm_h = wm_w
            wm_x = (width - wm_w) / 2
            wm_y = (height - wm_h) / 2
            try:
                canvas.setFillAlpha(0.05)
            except Exception:
                pass
            canvas.translate(width / 2.0, height / 2.0)
            canvas.rotate(30)
            canvas.translate(-width / 2.0, -height / 2.0)
            canvas.drawImage(logo_path, wm_x, wm_y, width=wm_w, height=wm_h, preserveAspectRatio=True, mask='auto')
        finally:
            canvas.restoreState()

    doc.build(elements, onFirstPage=_on_page, onLaterPages=_on_page)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    dispo = 'inline; filename=paiements_tranches_par_classe.pdf'
    if annee_scolaire:
        dispo = f'inline; filename=paiements_tranches_par_classe_{annee_scolaire}.pdf'
    response['Content-Disposition'] = dispo
    response.write(pdf)
    return response
