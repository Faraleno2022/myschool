from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import os
from django.conf import settings

# ReportLab for PDF exports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from .models import (
    Enseignant, AffectationClasse, PeriodeSalaire, 
    EtatSalaire, DetailHeuresClasse, TypeEnseignant
)
from .forms import EnseignantForm, AffectationClasseForm
from eleves.models import Ecole, Classe
from utilisateurs.utils import user_is_admin, user_school
from utilisateurs.permissions import can_add_teachers
from ecole_moderne.security_decorators import delete_permission_required, require_school_object

def _ecole_utilisateur(request):
    """Compat: utiliser l'utilitaire centralisé"""
    return user_school(request.user)

@login_required
def tableau_bord(request):
    """Tableau de bord du module Salaires"""
    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None

    # Statistiques générales
    base_qs = Enseignant.objects.all()
    if restreindre:
        base_qs = base_qs.filter(ecole=ecole_user)
    stats = {
        'total_enseignants': base_qs.count(),
        'enseignants_actifs': base_qs.filter(statut='ACTIF').count(),
        'enseignants_taux_horaire': base_qs.filter(type_enseignant='SECONDAIRE').count(),
        'enseignants_salaire_fixe': base_qs.exclude(type_enseignant='SECONDAIRE').count(),
    }
    
    # Période courante
    periode_courante = None
    try:
        now = timezone.now()
        periode_courante = PeriodeSalaire.objects.filter(
            mois=now.month,
            annee=now.year
        ).first()
    except:
        pass
    
    # États de salaire récents
    etats_recents = EtatSalaire.objects.select_related('enseignant', 'periode')
    if restreindre:
        etats_recents = etats_recents.filter(periode__ecole=ecole_user)
    etats_recents = etats_recents.order_by('-date_calcul')[:10]
    
    # Statistiques par école
    stats_ecoles = []
    ecoles_iter = Ecole.objects.all()
    if restreindre:
        ecoles_iter = ecoles_iter.filter(id=ecole_user.id)
    for ecole in ecoles_iter:
        enseignants_ecole = Enseignant.objects.filter(ecole=ecole, statut='ACTIF')
        stats_ecoles.append({
            'ecole': ecole,
            'total_enseignants': enseignants_ecole.count(),
            'taux_horaire': enseignants_ecole.filter(type_enseignant='SECONDAIRE').count(),
            'salaire_fixe': enseignants_ecole.exclude(type_enseignant='SECONDAIRE').count(),
        })
    
    # Alertes
    alertes = []
    
    # Vérifier les enseignants sans affectation active (période en cours)
    aujourd_hui = timezone.now().date()
    enseignants_base = Enseignant.objects.filter(statut='ACTIF')
    if restreindre:
        enseignants_base = enseignants_base.filter(ecole=ecole_user)
    enseignants_sans_affectation = (
        enseignants_base
        .annotate(
            nb_actives=Count(
                'affectations',
                filter=(
                    Q(affectations__actif=True,
                      affectations__date_debut__lte=aujourd_hui) &
                    (Q(affectations__date_fin__isnull=True) | Q(affectations__date_fin__gte=aujourd_hui))
                )
            )
        )
        .filter(nb_actives=0)
        .count()
    )
    
    if enseignants_sans_affectation > 0:
        alertes.append({
            'type': 'warning',
            'message': f'{enseignants_sans_affectation} enseignant(s) sans affectation de classe',
            'action': 'Gérer les affectations'
        })
    
    # Vérifier les périodes non clôturées
    periodes_ouvertes = PeriodeSalaire.objects.filter(cloturee=False).count()
    if periodes_ouvertes > 2:
        alertes.append({
            'type': 'info',
            'message': f'{periodes_ouvertes} périodes de salaire ouvertes',
            'action': 'Clôturer les anciennes périodes'
        })
    
    context = {
        'stats': stats,
        'periode_courante': periode_courante,
        'etats_recents': etats_recents,
        'stats_ecoles': stats_ecoles,
        'alertes': alertes,
    }
    
    return render(request, 'salaires/tableau_bord.html', context)


@login_required
def liste_enseignants(request):
    """Liste des enseignants avec filtres"""
    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None

    # Récupération des paramètres de filtrage
    search = request.GET.get('search', '')
    ecole_id = request.GET.get('ecole', '')
    type_enseignant = request.GET.get('type_enseignant', '')
    statut = request.GET.get('statut', '')
    
    # Construction de la requête
    enseignants = Enseignant.objects.select_related('ecole').prefetch_related('affectations__classe')
    if restreindre:
        enseignants = enseignants.filter(ecole=ecole_user)
    
    if search:
        enseignants = enseignants.filter(
            Q(nom__icontains=search) | 
            Q(prenoms__icontains=search) |
            Q(email__icontains=search)
        )
    
    if ecole_id:
        enseignants = enseignants.filter(ecole_id=ecole_id)
    
    if type_enseignant:
        enseignants = enseignants.filter(type_enseignant=type_enseignant)
    
    if statut:
        enseignants = enseignants.filter(statut=statut)
    
    # Pagination
    paginator = Paginator(enseignants, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Données pour les filtres
    ecoles = Ecole.objects.all()
    if restreindre:
        ecoles = ecoles.filter(id=ecole_user.id)
    types_enseignant = TypeEnseignant.choices
    
    # Statistiques des résultats filtrés
    stats = {
        'total_enseignants': enseignants.count(),
        'enseignants_actifs': enseignants.filter(statut='ACTIF').count(),
        'taux_horaire': enseignants.filter(type_enseignant='SECONDAIRE').count(),
        'salaire_fixe': enseignants.exclude(type_enseignant='SECONDAIRE').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'enseignants': page_obj,
        'ecoles': ecoles,
        'types_enseignant': types_enseignant,
        'stats': stats,
        'is_paginated': page_obj.has_other_pages(),
    }
    
    return render(request, 'salaires/liste_enseignants.html', context)


@login_required
def export_enseignants_csv(request):
    """Export CSV de la liste des enseignants en respectant les filtres"""
    search = request.GET.get('search', '')
    ecole_id = request.GET.get('ecole', '')
    type_enseignant = request.GET.get('type_enseignant', '')
    statut = request.GET.get('statut', '')

    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None
    enseignants = Enseignant.objects.select_related('ecole')
    if restreindre:
        enseignants = enseignants.filter(ecole=ecole_user)
    if search:
        enseignants = enseignants.filter(
            Q(nom__icontains=search) |
            Q(prenoms__icontains=search) |
            Q(email__icontains=search)
        )
    if ecole_id:
        enseignants = enseignants.filter(ecole_id=ecole_id)
    if type_enseignant:
        enseignants = enseignants.filter(type_enseignant=type_enseignant)
    if statut:
        enseignants = enseignants.filter(statut=statut)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="enseignants.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Ecole', 'Nom', 'Prénoms', 'Email', 'Téléphone', 'Type', 'Statut',
        'Salaire Fixe', 'Taux Horaire', 'Heures Mensuelles'
    ])

    for ens in enseignants.order_by('ecole__nom', 'nom'):
        writer.writerow([
            getattr(ens.ecole, 'nom', ''),
            ens.nom,
            ens.prenoms,
            ens.email or '',
            getattr(ens, 'telephone', ''),
            ens.type_enseignant,
            ens.statut,
            ens.salaire_fixe or '',
            ens.taux_horaire or '',
            ens.heures_mensuelles or ''
        ])

    return response


@login_required
def export_enseignants_pdf(request):
    """Export PDF de la liste des enseignants en respectant les mêmes filtres que la vue liste et CSV."""
    # Filtres
    search = request.GET.get('search', '')
    ecole_id = request.GET.get('ecole', '')
    type_enseignant = request.GET.get('type_enseignant', '')
    statut = request.GET.get('statut', '')

    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None
    enseignants = Enseignant.objects.select_related('ecole')
    if restreindre:
        enseignants = enseignants.filter(ecole=ecole_user)
    if search:
        enseignants = enseignants.filter(
            Q(nom__icontains=search) |
            Q(prenoms__icontains=search) |
            Q(email__icontains=search)
        )
    if ecole_id:
        enseignants = enseignants.filter(ecole_id=ecole_id)
    if type_enseignant:
        enseignants = enseignants.filter(type_enseignant=type_enseignant)
    if statut:
        enseignants = enseignants.filter(statut=statut)

    # Préparer la réponse HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="enseignants.pdf"'

    # Document (paysage pour meilleure lisibilité)
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=60, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        name='Cell',
        parent=styles['Normal'],
        fontSize=7,
        leading=8,
    )

    title_text = "Liste des enseignants"
    elements.append(Paragraph(title_text, styles['Title']))
    elements.append(Spacer(1, 0.5*cm))

    # Table avec largeurs de colonnes et wrap des textes
    data = [[
        'École', 'Nom', 'Prénoms', 'Email', 'Téléphone', 'Type', 'Statut',
        'Salaire Fixe', 'Taux Horaire', 'Heures Mensuelles'
    ]]

    def P(txt):
        return Paragraph(str(txt or ''), cell_style)

    # Abréviation des noms d'écoles pour économiser l'espace
    def _abbr_ecole(nom):
        n = str(nom or '')
        low = n.lower()
        campus = ''
        if 'somayah' in low:
            campus = 'Somayah'
        elif 'sonfonia' in low:
            campus = 'Sonfonia'
        base_is_hk = (
            'myschool' in low or 'h.k' in low or 'h k' in low or 'hk' in low or 'diané' in low or 'diane' in low
        )
        if base_is_hk and campus:
            return f"H. K DIANÉ – {campus}"
        return n

    for ens in enseignants.order_by('ecole__nom', 'nom'):
        data.append([
            _abbr_ecole(getattr(ens.ecole, 'nom', '') or ''),
            P(ens.nom),
            P(ens.prenoms),
            P(ens.email or ''),
            P(getattr(ens, 'telephone', '')),
            P(ens.type_enseignant),
            P(ens.statut),
            f"{ens.salaire_fixe:,}".replace(',', ' ') if ens.salaire_fixe is not None else '',
            f"{ens.taux_horaire:,}".replace(',', ' ') if ens.taux_horaire is not None else '',
            f"{ens.heures_mensuelles:,}".replace(',', ' ') if ens.heures_mensuelles is not None else ''
        ])

    col_widths = [
        3.4*cm,  # École (élargi pour éviter le retour à la ligne)
        2.6*cm,  # Nom
        3.2*cm,  # Prénoms
        4.2*cm,  # Email
        2.6*cm,  # Téléphone
        2.6*cm,  # Type
        2.2*cm,  # Statut
        2.6*cm,  # Salaire Fixe
        2.6*cm,  # Taux Horaire
        2.3*cm,  # Heures Mensuelles
    ]

    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        # Le corps utilise ParagraphStyle(Cell) à 7pt; on maintient ici pour les cellules non-Paragraph
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    elements.append(table)

    # Logo + filigrane
    logo_path = os.path.join(getattr(settings, 'BASE_DIR', ''), 'static', 'logos', 'logo.png')

    def _draw_header_and_watermark(canvas, doc_):
        # En-tête avec logo
        try:
            if os.path.exists(logo_path):
                canvas.drawImage(logo_path, doc_.leftMargin, doc_.pagesize[1]-40, width=30, height=30, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(doc_.leftMargin + 40, doc_.pagesize[1]-25, 'École Moderne myschool')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(doc_.pagesize[0]-doc_.rightMargin, doc_.pagesize[1]-25, title_text)

        # Filigrane avec logo (comme les autres documents)
        canvas.saveState()
        try:
            if os.path.exists(logo_path):
                # Taille ~150% de la largeur de page
                wm_width = doc_.pagesize[0] * 1.5
                wm_height = wm_width
                wm_x = (doc_.pagesize[0] - wm_width) / 2
                wm_y = (doc_.pagesize[1] - wm_height) / 2
                
                # Opacité visible mais discrète
                try:
                    canvas.setFillAlpha(0.15)
                except Exception:
                    pass
                
                # Rotation pour l'effet filigrane
                canvas.translate(doc_.pagesize[0] / 2.0, doc_.pagesize[1] / 2.0)
                canvas.rotate(30)
                canvas.translate(-doc_.pagesize[0] / 2.0, -doc_.pagesize[1] / 2.0)
                
                canvas.drawImage(logo_path, wm_x, wm_y, width=wm_width, height=wm_height, preserveAspectRatio=True, mask='auto')
            else:
                # Fallback vers texte si logo non trouvé
                canvas.setFont('Helvetica-Bold', 42)
                canvas.setFillGray(0.85)
                canvas.translate(doc_.pagesize[0]/2, doc_.pagesize[1]/2)
                canvas.rotate(30)
                canvas.drawCentredString(0, 0, 'H.K. DIANÉ')
        finally:
            canvas.restoreState()

    doc.build(elements, onFirstPage=_draw_header_and_watermark, onLaterPages=_draw_header_and_watermark)
    return response


@login_required
@require_school_object(model=Enseignant, pk_kwarg='enseignant_id', field_path='ecole')
def detail_enseignant(request, enseignant_id):
    """Détail d'un enseignant"""
    ecole_user = _ecole_utilisateur(request)
    qs = Enseignant.objects.all()
    if not user_is_admin(request.user) and ecole_user is not None:
        qs = qs.filter(ecole=ecole_user)
    enseignant = get_object_or_404(qs, id=enseignant_id)
    
    # Affectations actuelles
    affectations_actuelles = enseignant.affectations.filter(
        actif=True,
        date_debut__lte=timezone.now().date()
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=timezone.now().date())
    ).select_related('classe')
    
    # Historique des affectations
    historique_affectations = enseignant.affectations.exclude(
        id__in=affectations_actuelles.values_list('id', flat=True)
    ).select_related('classe').order_by('-date_debut')
    
    # États de salaire récents
    etats_salaire = enseignant.etats_salaire.select_related(
        'periode'
    ).order_by('-periode__annee', '-periode__mois')[:12]
    
    # Statistiques
    stats = {
        'total_affectations': enseignant.affectations.count(),
        'affectations_actuelles': affectations_actuelles.count(),
        'etats_salaire': enseignant.etats_salaire.count(),
        'etats_valides': enseignant.etats_salaire.filter(valide=True).count(),
    }
    
    # Calcul du salaire moyen si applicable
    if enseignant.etats_salaire.exists():
        stats['salaire_moyen'] = enseignant.etats_salaire.aggregate(
            moyenne=Avg('salaire_net')
        )['moyenne'] or 0
    else:
        stats['salaire_moyen'] = 0
    
    context = {
        'enseignant': enseignant,
        'affectations_actuelles': affectations_actuelles,
        'historique_affectations': historique_affectations,
        'etats_salaire': etats_salaire,
        'stats': stats,
    }
    
    return render(request, 'salaires/detail_enseignant.html', context)


@login_required
@require_school_object(model=Enseignant, pk_kwarg='enseignant_id', field_path='ecole')
def ajouter_affectation(request, enseignant_id):
    """Créer une affectation de classe pour un enseignant"""
    ecole_user = _ecole_utilisateur(request)
    qs = Enseignant.objects.all()
    if not user_is_admin(request.user) and ecole_user is not None:
        qs = qs.filter(ecole=ecole_user)
    enseignant = get_object_or_404(qs, id=enseignant_id)

    if request.method == 'POST':
        form = AffectationClasseForm(request.POST, enseignant=enseignant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Affectation créée avec succès.')
            return redirect('salaires:detail_enseignant', enseignant_id=enseignant.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = AffectationClasseForm(enseignant=enseignant)

    context = {
        'enseignant': enseignant,
        'form': form,
    }
    return render(request, 'salaires/affectation_form.html', context)


@login_required
@require_school_object(model=AffectationClasse, pk_kwarg='affectation_id', field_path='enseignant__ecole')
def clore_affectation(request, affectation_id):
    """Clore (désactiver) une affectation en mettant une date de fin à aujourd'hui"""
    affectation = get_object_or_404(
        AffectationClasse.objects.select_related('enseignant__ecole'),
        id=affectation_id
    )
    ecole_user = _ecole_utilisateur(request)
    if not user_is_admin(request.user) and ecole_user is not None and affectation.enseignant.ecole_id != ecole_user.id:
        messages.error(request, "Accès refusé.")
        return redirect('salaires:detail_enseignant', enseignant_id=affectation.enseignant_id)

    if request.method == 'POST':
        affectation.actif = False
        affectation.date_fin = timezone.now().date()
        affectation.save()
        messages.success(request, 'Affectation clôturée avec succès.')
    else:
        messages.error(request, "Méthode non autorisée.")
    return redirect('salaires:detail_enseignant', enseignant_id=affectation.enseignant_id)


@login_required
@delete_permission_required()
@require_school_object(model=AffectationClasse, pk_kwarg='affectation_id', field_path='enseignant__ecole')
def supprimer_affectation(request, affectation_id):
    """Supprimer une affectation (si besoin)"""
    affectation = get_object_or_404(
        AffectationClasse.objects.select_related('enseignant__ecole'),
        id=affectation_id
    )
    ecole_user = _ecole_utilisateur(request)
    if not user_is_admin(request.user) and ecole_user is not None and affectation.enseignant.ecole_id != ecole_user.id:
        messages.error(request, "Accès refusé.")
        return redirect('salaires:detail_enseignant', enseignant_id=affectation.enseignant_id)

    if request.method == 'POST':
        enseignant_id = affectation.enseignant_id
        affectation.delete()
        messages.success(request, 'Affectation supprimée.')
        return redirect('salaires:detail_enseignant', enseignant_id=enseignant_id)
    else:
        messages.error(request, "Méthode non autorisée.")
        return redirect('salaires:detail_enseignant', enseignant_id=affectation.enseignant_id)


@login_required
def etats_salaire(request):
    """Liste des états de salaire avec filtres"""
    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None

    # Récupération des paramètres de filtrage
    periode_id = request.GET.get('periode', '')
    ecole_id = request.GET.get('ecole', '')
    enseignant_id = request.GET.get('enseignant', '')
    statut = request.GET.get('statut', '')
    search = request.GET.get('search', '')
    
    # Construction de la requête
    etats = EtatSalaire.objects.select_related('enseignant', 'periode', 'periode__ecole')
    if restreindre:
        etats = etats.filter(periode__ecole=ecole_user)
    
    if periode_id:
        etats = etats.filter(periode_id=periode_id)
    
    if ecole_id:
        etats = etats.filter(periode__ecole_id=ecole_id)
    
    if enseignant_id:
        etats = etats.filter(enseignant_id=enseignant_id)
    
    if statut == 'valide':
        etats = etats.filter(valide=True)
    elif statut == 'en_attente':
        etats = etats.filter(valide=False)
    elif statut == 'paye':
        etats = etats.filter(paye=True)
    elif statut == 'non_paye':
        etats = etats.filter(paye=False)
    
    if search:
        etats = etats.filter(
            Q(enseignant__nom__icontains=search) |
            Q(enseignant__prenoms__icontains=search)
        )
    
    # Tri par défaut
    etats = etats.order_by('-periode__annee', '-periode__mois', 'enseignant__nom')

    # Fallback intelligent: si aucun filtre n'est appliqué et que la requête est vide,
    # afficher les états des 3 dernières périodes disponibles (par école si restreint)
    filters_applied = any([periode_id, ecole_id, enseignant_id, statut, search])
    if not filters_applied and not etats.exists():
        periodes_recent = PeriodeSalaire.objects.order_by('-annee', '-mois')
        if restreindre:
            periodes_recent = periodes_recent.filter(ecole=ecole_user)
        recent_ids = list(periodes_recent.values_list('id', flat=True)[:3])
        if recent_ids:
            etats = (
                EtatSalaire.objects.select_related('enseignant', 'periode', 'periode__ecole')
                .filter(periode_id__in=recent_ids)
                .order_by('-periode__annee', '-periode__mois', 'enseignant__nom')
            )
    
    # Si toujours aucun résultat, vérifier s'il y a des périodes créées
    no_periods_exist = False
    periode_selected_exists = False
    if not etats.exists():
        periodes_count = PeriodeSalaire.objects.all()
        if restreindre:
            periodes_count = periodes_count.filter(ecole=ecole_user)
        no_periods_exist = periodes_count.count() == 0
        
        # Vérifier si une période spécifique est sélectionnée et existe
        if periode_id:
            try:
                periode_selected = PeriodeSalaire.objects.get(id=periode_id)
                if not restreindre or periode_selected.ecole == ecole_user:
                    periode_selected_exists = True
            except PeriodeSalaire.DoesNotExist:
                pass
    
    # Pagination
    paginator = Paginator(etats, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Données pour les filtres
    periodes = PeriodeSalaire.objects.order_by('-annee', '-mois')
    if restreindre:
        periodes = periodes.filter(ecole=ecole_user)
    ecoles = Ecole.objects.all()
    if restreindre:
        ecoles = ecoles.filter(id=ecole_user.id)
    
    # Statistiques des résultats filtrés
    totaux = {
        'total_etats': etats.count(),
        'montant_total': etats.aggregate(total=Sum('salaire_net'))['total'] or 0,
        'en_attente': etats.filter(valide=False).count(),
        'payes': etats.filter(paye=True).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'etats': page_obj,
        'periodes': periodes,
        'ecoles': ecoles,
        'totaux': totaux,
        'is_paginated': page_obj.has_other_pages(),
        'no_periods_exist': no_periods_exist,
        'periode_selected_exists': periode_selected_exists,
        # Conserver les filtres sélectionnés
        'periode_selectionnee': periode_id,
        'ecole_selectionnee': ecole_id,
        'statut_selectionne': statut,
    }
    return render(request, 'salaires/etats_salaire.html', context)

@login_required
def export_etats_salaire_csv(request):
    """Export CSV des états de salaire en respectant exactement les filtres de la vue liste."""
    # Filtres identiques à etats_salaire()
    periode_id = request.GET.get('periode', '')
    ecole_id = request.GET.get('ecole', '')
    statut = request.GET.get('statut', '')
    search = request.GET.get('search', '')

    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None
    etats = EtatSalaire.objects.select_related('enseignant', 'periode', 'periode__ecole')
    if restreindre:
        etats = etats.filter(periode__ecole=ecole_user)

    if periode_id:
        etats = etats.filter(periode_id=periode_id)
    if ecole_id:
        etats = etats.filter(periode__ecole_id=ecole_id)
    if statut == 'valide':
        etats = etats.filter(valide=True)
    elif statut == 'en_attente':
        etats = etats.filter(valide=False)
    elif statut == 'paye':
        etats = etats.filter(paye=True)
    elif statut == 'non_paye':
        etats = etats.filter(paye=False)
    if search:
        etats = etats.filter(
            Q(enseignant__nom__icontains=search) |
            Q(enseignant__prenoms__icontains=search)
        )

    etats = etats.order_by('-periode__annee', '-periode__mois', 'enseignant__nom')

    # Générer le CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="etats_salaire.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Ecole', 'Periode', 'Enseignant', 'Type', 'Valide', 'Payé',
        'Salaire Base', 'Salaire Net', 'Total Heures', 'Date Calcul'
    ])

    for e in etats:
        writer.writerow([
            getattr(e.periode.ecole, 'nom', ''),
            f"{e.periode.mois:02d}/{e.periode.annee}",
            getattr(e.enseignant, 'nom_complet', str(e.enseignant)),
            getattr(e.enseignant, 'type_enseignant', ''),
            'Oui' if e.valide else 'Non',
            'Oui' if e.paye else 'Non',
            e.salaire_base,
            e.salaire_net,
            e.total_heures if e.total_heures is not None else '',
            e.date_calcul.strftime('%Y-%m-%d %H:%M') if e.date_calcul else ''
        ])

    return response

@login_required
def export_etats_salaire_pdf(request):
    """Export PDF des états de salaire avec les mêmes filtres, en-tête logo et filigrane."""
    # Filtres
    periode_id = request.GET.get('periode', '')
    ecole_id = request.GET.get('ecole', '')
    statut = request.GET.get('statut', '')
    search = request.GET.get('search', '')

    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None
    etats = EtatSalaire.objects.select_related('enseignant', 'periode', 'periode__ecole')
    if restreindre:
        etats = etats.filter(periode__ecole=ecole_user)
    if periode_id:
        etats = etats.filter(periode_id=periode_id)
    if ecole_id:
        etats = etats.filter(periode__ecole_id=ecole_id)
    if statut == 'valide':
        etats = etats.filter(valide=True)
    elif statut == 'en_attente':
        etats = etats.filter(valide=False)
    elif statut == 'paye':
        etats = etats.filter(paye=True)
    elif statut == 'non_paye':
        etats = etats.filter(paye=False)
    if search:
        etats = etats.filter(
            Q(enseignant__nom__icontains=search) |
            Q(enseignant__prenoms__icontains=search)
        )

    etats = etats.order_by('-periode__annee', '-periode__mois', 'enseignant__nom')

    # Préparer la réponse HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="etats_salaire.pdf"'

    # Document (paysage pour meilleure lisibilité)
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=60, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    title_text = "États de salaire"
    elements.append(Paragraph(title_text, styles['Title']))
    elements.append(Spacer(1, 0.5*cm))

    # Table
    data = [[
        'École', 'Période', 'Enseignant', 'Type', 'Valide', 'Payé',
        'Salaire Base', 'Salaire Net', 'Total Heures', 'Date Calcul'
    ]]
    for e in etats:
        data.append([
            getattr(e.periode.ecole, 'nom', ''),
            f"{e.periode.mois:02d}/{e.periode.annee}",
            getattr(e.enseignant, 'nom_complet', str(e.enseignant)),
            getattr(e.enseignant, 'type_enseignant', ''),
            'Oui' if e.valide else 'Non',
            'Oui' if e.paye else 'Non',
            e.salaire_base,
            e.salaire_net,
            e.total_heures if e.total_heures is not None else '',
            e.date_calcul.strftime('%Y-%m-%d %H:%M') if e.date_calcul else ''
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(table)

    # Logo + filigrane
    logo_path = os.path.join(getattr(settings, 'BASE_DIR', ''), 'static', 'logos', 'logo.png')

    def _draw_header_and_watermark(canvas, doc_):
        # En-tête avec logo
        try:
            if os.path.exists(logo_path):
                canvas.drawImage(logo_path, doc_.leftMargin, doc_.pagesize[1]-40, width=30, height=30, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(doc_.leftMargin + 40, doc_.pagesize[1]-25, 'École Moderne myschool')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(doc_.pagesize[0]-doc_.rightMargin, doc_.pagesize[1]-25, title_text)

        # Filigrane avec logo (comme les autres documents)
        canvas.saveState()
        try:
            if os.path.exists(logo_path):
                # Taille ~150% de la largeur de page
                wm_width = doc_.pagesize[0] * 1.5
                wm_height = wm_width
                wm_x = (doc_.pagesize[0] - wm_width) / 2
                wm_y = (doc_.pagesize[1] - wm_height) / 2
                
                # Opacité visible mais discrète
                try:
                    canvas.setFillAlpha(0.15)
                except Exception:
                    pass
                
                # Rotation pour l'effet filigrane
                canvas.translate(doc_.pagesize[0] / 2.0, doc_.pagesize[1] / 2.0)
                canvas.rotate(30)
                canvas.translate(-doc_.pagesize[0] / 2.0, -doc_.pagesize[1] / 2.0)
                
                canvas.drawImage(logo_path, wm_x, wm_y, width=wm_width, height=wm_height, preserveAspectRatio=True, mask='auto')
            else:
                # Fallback vers texte si logo non trouvé
                canvas.setFont('Helvetica-Bold', 42)
                canvas.setFillGray(0.85)
                canvas.translate(doc_.pagesize[0]/2, doc_.pagesize[1]/2)
                canvas.rotate(30)
                canvas.drawCentredString(0, 0, 'H.K. DIANÉ')
        finally:
            canvas.restoreState()

    doc.build(elements, onFirstPage=_draw_header_and_watermark, onLaterPages=_draw_header_and_watermark)
    return response


@login_required
@require_school_object(model=PeriodeSalaire, pk_kwarg='periode_id', field_path='ecole')
def calculer_salaires(request, periode_id):
    """Calculer les salaires pour une période"""
    
    periode = get_object_or_404(PeriodeSalaire, id=periode_id)
    
    if periode.cloturee:
        messages.error(request, "Impossible de calculer les salaires d'une période clôturée.")
        return redirect('salaires:etats_salaire')
    
    # Accepter GET et POST pour le calcul
    if request.method in ['GET', 'POST']:
        try:
            # Récupérer tous les enseignants actifs de l'école
            enseignants = Enseignant.objects.filter(
                ecole=periode.ecole,
                statut='ACTIF'
            )
            
            calculs_effectues = 0
            
            for enseignant in enseignants:
                # Vérifier si l'état de salaire existe déjà
                etat_salaire, created = EtatSalaire.objects.get_or_create(
                    enseignant=enseignant,
                    periode=periode,
                    defaults={
                        'calcule_par': request.user,
                        'salaire_base': Decimal('0'),
                        'salaire_net': Decimal('0'),
                    }
                )
                
                if created or not etat_salaire.valide:
                    # Calculer le salaire selon le type d'enseignant
                    if enseignant.est_salaire_fixe:
                        # Salaire fixe
                        etat_salaire.salaire_base = enseignant.salaire_fixe or Decimal('0')
                        etat_salaire.total_heures = None
                    else:
                        # Taux horaire - utiliser les heures mensuelles définies
                        # Utiliser les heures mensuelles de l'enseignant ou la valeur par défaut
                        total_heures = enseignant.heures_mensuelles_effectives
                        
                        # Supprimer les anciens détails
                        etat_salaire.details_heures.all().delete()
                        
                        # Récupérer les affectations actives pour créer les détails
                        affectations = enseignant.affectations.filter(
                            actif=True,
                            date_debut__lte=timezone.now().date()
                        ).filter(
                            Q(date_fin__isnull=True) | Q(date_fin__gte=timezone.now().date())
                        )
                        
                        # Si l'enseignant a des affectations, répartir les heures
                        if affectations.exists():
                            heures_par_affectation = total_heures / len(affectations)
                            for affectation in affectations:
                                # Créer le détail des heures
                                DetailHeuresClasse.objects.create(
                                    etat_salaire=etat_salaire,
                                    affectation_classe=affectation,
                                    heures_prevues=heures_par_affectation,
                                    heures_realisees=heures_par_affectation,
                                    taux_horaire_applique=enseignant.taux_horaire or Decimal('0'),
                                )
                        else:
                            # Pas d'affectation, créer un détail générique
                            DetailHeuresClasse.objects.create(
                                etat_salaire=etat_salaire,
                                affectation_classe=None,
                                heures_prevues=total_heures,
                                heures_realisees=total_heures,
                                taux_horaire_applique=enseignant.taux_horaire or Decimal('0'),
                            )
                        
                        etat_salaire.total_heures = total_heures
                        etat_salaire.salaire_base = total_heures * (enseignant.taux_horaire or Decimal('0'))
                    
                    # Sauvegarder (le salaire_net sera calculé automatiquement)
                    etat_salaire.calcule_par = request.user
                    etat_salaire.save()
                    
                    calculs_effectues += 1
            
            messages.success(
                request, 
                f"Calcul des salaires terminé. {calculs_effectues} état(s) de salaire calculé(s)."
            )
            
        except Exception as e:
            messages.error(request, f"Erreur lors du calcul des salaires : {str(e)}")
    
    return redirect('salaires:etats_salaire')


@login_required
def valider_etat_salaire(request, etat_id):
    """Valider un état de salaire"""
    
    etat = get_object_or_404(EtatSalaire, id=etat_id)
    
    if not etat.peut_etre_valide:
        messages.error(request, "Cet état de salaire ne peut pas être validé.")
        return redirect('salaires:etats_salaire')
    
    if request.method == 'POST':
        etat.valide = True
        etat.valide_par = request.user
        etat.date_validation = timezone.now()
        etat.save()
        
        messages.success(request, f"État de salaire de {etat.enseignant.nom_complet} validé avec succès.")
    
    return redirect('salaires:etats_salaire')


@login_required
def marquer_paye(request, etat_id):
    """Marquer un état de salaire comme payé"""
    
    etat = get_object_or_404(EtatSalaire, id=etat_id)
    
    if not etat.peut_etre_paye:
        messages.error(request, "Cet état de salaire ne peut pas être marqué comme payé.")
        return redirect('salaires:etats_salaire')
    
    if request.method == 'POST':
        etat.paye = True
        etat.date_paiement = timezone.now()
        etat.save()
        
        messages.success(request, f"État de salaire de {etat.enseignant.nom_complet} marqué comme payé.")
    
    return redirect('salaires:etats_salaire')


@login_required
def fiche_paie_pdf(request, etat_id):
    """Génère une fiche de paie PDF pour un état de salaire"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    from django.http import HttpResponse
    from datetime import datetime
    
    etat = get_object_or_404(EtatSalaire, id=etat_id)
    
    # Vérifier les permissions
    ecole_user = _ecole_utilisateur(request)
    if not user_is_admin(request.user) and ecole_user and etat.periode.ecole != ecole_user:
        raise Http404("État de salaire non trouvé")
    
    # Créer la réponse HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="fiche_paie_{etat.enseignant.nom}_{etat.periode.mois}_{etat.periode.annee}.pdf"'
    
    # Créer le PDF
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    
    # Ajouter le logo en filigrane
    from ecole_moderne.pdf_utils import draw_logo_watermark
    draw_logo_watermark(p, width, height, opacity=0.06, rotate=30, scale=1.2)
    
    # En-tête avec logo
    try:
        logo_path = os.path.join(settings.STATIC_ROOT or settings.STATICFILES_DIRS[0], 'logos', 'logo.png')
        if os.path.exists(logo_path):
            p.drawImage(logo_path, 2*cm, height-4*cm, width=3*cm, height=2*cm)
    except:
        pass
    
    # Titre - Nom de l'école centré avec police réduite
    p.setFont("Helvetica-Bold", 14)
    text_width = p.stringWidth(etat.periode.ecole.nom, "Helvetica-Bold", 14)
    p.drawString((width - text_width) / 2, height-2.5*cm, f"{etat.periode.ecole.nom}")
    
    # Sous-titre FICHE DE PAIE centré
    p.setFont("Helvetica-Bold", 16)
    fiche_text = "FICHE DE PAIE"
    fiche_width = p.stringWidth(fiche_text, "Helvetica-Bold", 16)
    p.drawString((width - fiche_width) / 2, height-3*cm, fiche_text)
    
    # Informations période
    p.setFont("Helvetica", 12)
    p.drawString(6*cm, height-3.5*cm, f"Période: {etat.periode.mois}/{etat.periode.annee}")
    p.drawString(6*cm, height-4*cm, f"Date d'édition: {datetime.now().strftime('%d/%m/%Y')}")
    
    # Informations enseignant
    y_pos = height - 6*cm
    p.setFont("Helvetica-Bold", 12)
    p.drawString(2*cm, y_pos, "INFORMATIONS ENSEIGNANT")
    
    y_pos -= 0.8*cm
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, y_pos, f"Nom: {etat.enseignant.nom} {etat.enseignant.prenoms}")
    y_pos -= 0.5*cm
    p.drawString(2*cm, y_pos, f"Téléphone: {etat.enseignant.telephone or 'Non renseigné'}")
    y_pos -= 0.5*cm
    p.drawString(2*cm, y_pos, f"Email: {etat.enseignant.email or 'Non renseigné'}")
    y_pos -= 0.5*cm
    p.drawString(2*cm, y_pos, f"Type: {'Salaire fixe' if etat.enseignant.est_salaire_fixe else 'Taux horaire'}")
    
    # Détails du salaire
    y_pos -= 1.5*cm
    p.setFont("Helvetica-Bold", 12)
    p.drawString(2*cm, y_pos, "DÉTAILS DU SALAIRE")
    
    # Tableau des montants
    data = [
        ['Élément', 'Montant (GNF)'],
        ['Salaire de base', f"{etat.salaire_base:,.0f}".replace(',', ' ')],
    ]
    
    if etat.total_heures:
        data.append(['Heures travaillées', f"{etat.total_heures}h"])
        data.append(['Taux horaire', f"{etat.enseignant.taux_horaire or 0:,.0f}".replace(',', ' ')])
    
    if etat.primes:
        data.append(['Primes', f"{etat.primes:,.0f}".replace(',', ' ')])
    
    if etat.deductions:
        data.append(['Déductions', f"-{etat.deductions:,.0f}".replace(',', ' ')])
    
    data.append(['SALAIRE NET', f"{etat.salaire_net:,.0f}".replace(',', ' ')])
    
    # Créer le tableau
    y_pos -= 0.8*cm
    table = Table(data, colWidths=[8*cm, 4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    table.wrapOn(p, width, height)
    table.drawOn(p, 2*cm, y_pos - len(data) * 0.6*cm)
    
    # Statut
    y_pos -= (len(data) + 2) * 0.6*cm
    p.setFont("Helvetica-Bold", 10)
    statut_text = "VALIDÉ" if etat.valide else "EN ATTENTE DE VALIDATION"
    if etat.paye:
        statut_text += " - PAYÉ"
    p.drawString(2*cm, y_pos, f"Statut: {statut_text}")
    
    if etat.valide and etat.date_validation:
        y_pos -= 0.5*cm
        p.setFont("Helvetica", 9)
        p.drawString(2*cm, y_pos, f"Validé le {etat.date_validation.strftime('%d/%m/%Y')} par {etat.valide_par}")
    
    if etat.paye and etat.date_paiement:
        y_pos -= 0.5*cm
        p.drawString(2*cm, y_pos, f"Payé le {etat.date_paiement.strftime('%d/%m/%Y')}")
    
    # Section signatures
    y_pos -= 3*cm
    p.setFont("Helvetica-Bold", 12)
    p.drawString(2*cm, y_pos, "SIGNATURES")
    
    # Ligne de séparation
    y_pos -= 0.5*cm
    p.line(2*cm, y_pos, width-2*cm, y_pos)
    
    # Signatures côte à côte
    y_pos -= 1*cm
    
    # Signature enseignant (gauche)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2*cm, y_pos, "L'ENSEIGNANT")
    p.setFont("Helvetica", 9)
    p.drawString(2*cm, y_pos-0.4*cm, f"Nom: {etat.enseignant.nom} {etat.enseignant.prenoms}")
    
    # Cadre pour signature enseignant
    signature_width = 6*cm
    signature_height = 2*cm
    p.rect(2*cm, y_pos-3*cm, signature_width, signature_height)
    p.setFont("Helvetica", 8)
    p.drawString(2*cm + 0.2*cm, y_pos-3.2*cm, "Signature et date:")
    
    # Signature comptable (droite)
    comptable_x = width - 8*cm
    p.setFont("Helvetica-Bold", 10)
    p.drawString(comptable_x, y_pos, "LE COMPTABLE")
    p.setFont("Helvetica", 9)
    if etat.calcule_par:
        p.drawString(comptable_x, y_pos-0.4*cm, f"Nom: {etat.calcule_par.get_full_name() or etat.calcule_par.username}")
    else:
        p.drawString(comptable_x, y_pos-0.4*cm, "Nom: _________________")
    
    # Cadre pour signature comptable
    p.rect(comptable_x, y_pos-3*cm, signature_width, signature_height)
    p.setFont("Helvetica", 8)
    p.drawString(comptable_x + 0.2*cm, y_pos-3.2*cm, "Signature et date:")
    
    # Pied de page
    p.setFont("Helvetica", 8)
    p.drawString(2*cm, 2*cm, f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    p.drawString(2*cm, 1.5*cm, "Ce document est confidentiel et ne doit pas être divulgué à des tiers.")
    
    p.showPage()
    p.save()
    
    return response


@login_required
def gestion_periodes(request):
    """Gestion des périodes de salaire"""
    
    # Récupération des paramètres de filtrage
    ecole_id = request.GET.get('ecole', '')
    annee = request.GET.get('annee', '')
    statut = request.GET.get('statut', '')  # 'cloture' | 'ouvert' | ''
    
    # Construction de la requête
    periodes = PeriodeSalaire.objects.select_related('ecole').prefetch_related('etats_salaire')

    # Restriction par école pour les non-admins
    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None
    if restreindre:
        periodes = periodes.filter(ecole=ecole_user)
    
    if ecole_id:
        periodes = periodes.filter(ecole_id=ecole_id)
    
    if annee:
        periodes = periodes.filter(annee=annee)
    
    # Filtre statut ouvert/clôturé
    if statut == 'cloture':
        periodes = periodes.filter(cloturee=True)
    elif statut == 'ouvert':
        periodes = periodes.filter(cloturee=False)
    
    periodes = periodes.order_by('-annee', '-mois')

    # Fallback: si aucun filtre n'est appliqué et aucune période trouvée,
    # charger les 6 dernières périodes disponibles (restreintes à l'école de l'utilisateur si nécessaire)
    filtres_appliques = any([ecole_id, annee, statut])
    if not filtres_appliques and not periodes.exists():
        fallback_base = PeriodeSalaire.objects.select_related('ecole')
        if restreindre:
            fallback_base = fallback_base.filter(ecole=ecole_user)
        fallback_ids = list(
            fallback_base.order_by('-annee', '-mois').values_list('id', flat=True)[:6]
        )
        periodes = (
            PeriodeSalaire.objects
            .select_related('ecole')
            .prefetch_related('etats_salaire')
            .filter(id__in=fallback_ids)
            .order_by('-annee', '-mois')
        )
    
    # Ajout des statistiques pour chaque période
    for periode in periodes:
        periode.etats_valides = periode.etats_salaire.filter(valide=True).count()
        periode.etats_payes = periode.etats_salaire.filter(paye=True).count()
    
    # Pagination
    paginator = Paginator(periodes, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Données pour les filtres
    ecoles = Ecole.objects.all()
    if restreindre and ecole_user:
        ecoles = ecoles.filter(id=ecole_user.id)
    annees_disponibles = PeriodeSalaire.objects.values_list('annee', flat=True).distinct().order_by('-annee')
    
    # Statistiques
    from django.db.models import Count
    # Utiliser une requête de base non-slicée pour les stats globales si besoin
    base_stats_qs = PeriodeSalaire.objects.all()
    if restreindre and ecole_user:
        base_stats_qs = base_stats_qs.filter(ecole=ecole_user)
    if ecole_id:
        base_stats_qs = base_stats_qs.filter(ecole_id=ecole_id)
    if annee:
        base_stats_qs = base_stats_qs.filter(annee=annee)
    if statut == 'cloture':
        base_stats_qs = base_stats_qs.filter(cloturee=True)
    elif statut == 'ouvert':
        base_stats_qs = base_stats_qs.filter(cloturee=False)

    total_etats = EtatSalaire.objects.filter(periode__in=base_stats_qs).count()
    
    stats = {
        'total_periodes': base_stats_qs.count(),
        'periodes_ouvertes': base_stats_qs.filter(cloturee=False).count(),
        'periodes_cloturees': base_stats_qs.filter(cloturee=True).count(),
        'etats_calcules': total_etats,
    }
    
    # Période courante (première ouverte la plus récente) pour styling
    try:
        periode_courante = (
            PeriodeSalaire.objects.filter(cloturee=False, **({'ecole': ecole_user} if restreindre else {}))
            .order_by('-annee', '-mois')
            .first()
        )
    except Exception:
        periode_courante = None

    context = {
        'page_obj': page_obj,
        'periodes': page_obj,
        'ecoles': ecoles,
        'annees_disponibles': annees_disponibles,
        'stats': stats,
        'periode_courante': periode_courante,
        'is_paginated': page_obj.has_other_pages(),
    }
    
    return render(request, 'salaires/gestion_periodes.html', context)


@login_required
def rapport_paiements(request):
    """Rapport des salaires payés: totaux par mois et par année, avec filtres."""
    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None

    annee = request.GET.get('annee', '')
    ecole_id = request.GET.get('ecole', '')

    qs = EtatSalaire.objects.filter(paye=True).select_related('periode', 'periode__ecole')
    if restreindre:
        qs = qs.filter(periode__ecole=ecole_user)
    if annee:
        qs = qs.filter(periode__annee=annee)
    if ecole_id:
        qs = qs.filter(periode__ecole_id=ecole_id)

    # Agrégation par année/mois de la période de salaire
    aggs = (
        qs.values('periode__annee', 'periode__mois')
          .annotate(total_paye=Sum('salaire_net'), nombre=Count('id'))
          .order_by('-periode__annee', '-periode__mois')
    )

    # Totaux globaux
    total_annuel = qs.aggregate(total=Sum('salaire_net'))['total'] or 0

    # Filtres disponibles
    annees_dispo = (PeriodeSalaire.objects
                    .order_by('-annee')
                    .values_list('annee', flat=True)
                    .distinct())
    ecoles = Ecole.objects.all()
    if restreindre and ecole_user:
        ecoles = ecoles.filter(id=ecole_user.id)

    context = {
        'aggs': aggs,
        'total_annuel': total_annuel,
        'annees_dispo': annees_dispo,
        'ecoles': ecoles,
        'annee_selectionnee': annee,
        'ecole_selectionnee': ecole_id,
    }
    return render(request, 'salaires/rapport_paiements.html', context)


@login_required
def export_rapport_paiements_pdf(request):
    """Export PDF du rapport des salaires payés (paysage)."""
    ecole_user = _ecole_utilisateur(request)
    restreindre = not user_is_admin(request.user) and ecole_user is not None

    annee = request.GET.get('annee', '')
    ecole_id = request.GET.get('ecole', '')

    qs = EtatSalaire.objects.filter(paye=True).select_related('periode', 'periode__ecole')
    if restreindre:
        qs = qs.filter(periode__ecole=ecole_user)
    if annee:
        qs = qs.filter(periode__annee=annee)
    if ecole_id:
        qs = qs.filter(periode__ecole_id=ecole_id)

    aggs = (
        qs.values('periode__annee', 'periode__mois')
          .annotate(total_paye=Sum('salaire_net'), nombre=Count('id'))
          .order_by('periode__annee', 'periode__mois')
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_paiements.pdf"'

    # Créer un template avec filigrane
    class WatermarkDocTemplate(SimpleDocTemplate):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
        
        def afterPage(self):
            c = self.canv
            try:
                from ecole_moderne.pdf_utils import draw_logo_watermark
                draw_logo_watermark(c, self.pagesize[0], self.pagesize[1])
            except Exception:
                pass
    
    doc = WatermarkDocTemplate(response, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=60, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Ajouter le logo en en-tête
    try:
        from django.contrib.staticfiles import finders
        logo_path = finders.find('logos/logo.png')
        if logo_path:
            from reportlab.platypus import Image
            logo = Image(logo_path, width=60, height=60)
            elements.append(logo)
            elements.append(Spacer(1, 10))
    except Exception:
        pass

    titre = "Rapport des salaires payés"
    if annee:
        titre += f" - {annee}"
    elements.append(Paragraph(titre, styles['Title']))
    elements.append(Spacer(1, 0.5*cm))

    data = [['Année', 'Mois', 'Total payé (GNF)', 'Nombre d\'états payés']]
    for row in aggs:
        data.append([
            row['periode__annee'],
            f"{row['periode__mois']:02d}",
            f"{row['total_paye']:,}".replace(',', ' '),
            row['nombre'],
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(table)

    logo_path = os.path.join(getattr(settings, 'BASE_DIR', ''), 'static', 'logos', 'logo.png')

    def _draw_header_and_watermark(canvas, doc_):
        try:
            if os.path.exists(logo_path):
                canvas.drawImage(logo_path, doc_.leftMargin, doc_.pagesize[1]-40, width=30, height=30, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(doc_.leftMargin + 40, doc_.pagesize[1]-25, 'École Moderne myschool')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(doc_.pagesize[0]-doc_.rightMargin, doc_.pagesize[1]-25, titre)

        # Filigrane avec logo (comme les autres documents)
        canvas.saveState()
        try:
            if os.path.exists(logo_path):
                # Taille ~150% de la largeur de page
                wm_width = doc_.pagesize[0] * 1.5
                wm_height = wm_width
                wm_x = (doc_.pagesize[0] - wm_width) / 2
                wm_y = (doc_.pagesize[1] - wm_height) / 2
                
                # Opacité visible mais discrète
                try:
                    canvas.setFillAlpha(0.15)
                except Exception:
                    pass
                
                # Rotation pour l'effet filigrane
                canvas.translate(doc_.pagesize[0] / 2.0, doc_.pagesize[1] / 2.0)
                canvas.rotate(30)
                canvas.translate(-doc_.pagesize[0] / 2.0, -doc_.pagesize[1] / 2.0)
                
                canvas.drawImage(logo_path, wm_x, wm_y, width=wm_width, height=wm_height, preserveAspectRatio=True, mask='auto')
            else:
                # Fallback vers texte si logo non trouvé
                canvas.setFont('Helvetica-Bold', 42)
                canvas.setFillGray(0.85)
                canvas.translate(doc_.pagesize[0]/2, doc_.pagesize[1]/2)
                canvas.rotate(30)
                canvas.drawCentredString(0, 0, 'H.K. DIANÉ')
        finally:
            canvas.restoreState()

    doc.build(elements, onFirstPage=_draw_header_and_watermark, onLaterPages=_draw_header_and_watermark)
    return response


@login_required
def creer_periode(request):
    """Création d'une nouvelle période de salaire"""
    if request.method == 'POST':
        try:
            mois = int(request.POST.get('mois'))
            annee = int(request.POST.get('annee'))
            ecole_id = int(request.POST.get('ecole'))
            nombre_semaines = Decimal(request.POST.get('nombre_semaines', '4.33'))
            
            # Validation des données
            if not (1 <= mois <= 12):
                messages.error(request, "Le mois doit être entre 1 et 12.")
                return redirect('salaires:gestion_periodes')
            
            if annee < 2020 or annee > 2030:
                messages.error(request, "L'année doit être entre 2020 et 2030.")
                return redirect('salaires:gestion_periodes')
            
            # Récupérer l'école
            from eleves.models import Ecole
            ecole = get_object_or_404(Ecole, id=ecole_id)
            
            # Vérifier si la période existe déjà
            periode_existante = PeriodeSalaire.objects.filter(
                mois=mois,
                annee=annee,
                ecole=ecole
            ).exists()
            
            if periode_existante:
                messages.error(
                    request, 
                    f"Une période pour {mois}/{annee} existe déjà pour {ecole.nom}."
                )
                return redirect('salaires:gestion_periodes')
            
            # Créer la nouvelle période
            nouvelle_periode = PeriodeSalaire.objects.create(
                mois=mois,
                annee=annee,
                ecole=ecole,
                nombre_semaines=nombre_semaines,
                cree_par=request.user
            )
            
            messages.success(
                request, 
                f"Période {nouvelle_periode} créée avec succès !"
            )
            
        except (ValueError, TypeError) as e:
            messages.error(request, "Données invalides. Veuillez vérifier les champs.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la création : {str(e)}")
    
    return redirect('salaires:gestion_periodes')


@login_required
def cloturer_periode(request, periode_id):
    """Clôture d'une période de salaire et crée automatiquement la période suivante"""
    if request.method == 'POST':
        try:
            periode = get_object_or_404(PeriodeSalaire, id=periode_id)
            
            # Vérifier que la période n'est pas déjà clôturée
            if periode.cloturee:
                messages.warning(request, f"La période {periode} est déjà clôturée.")
                return redirect('salaires:gestion_periodes')
            
            # Clôturer la période actuelle
            periode.cloturee = True
            periode.date_cloture = timezone.now()
            periode.cloturee_par = request.user
            periode.save()
            
            # Calculer le mois et l'année suivants
            mois_suivant = periode.mois + 1
            annee_suivante = periode.annee
            
            if mois_suivant > 12:
                mois_suivant = 1
                annee_suivante += 1
            
            # Vérifier si la période suivante existe déjà
            periode_suivante_existe = PeriodeSalaire.objects.filter(
                mois=mois_suivant,
                annee=annee_suivante,
                ecole=periode.ecole
            ).exists()
            
            if not periode_suivante_existe:
                # Créer automatiquement la période suivante
                nouvelle_periode = PeriodeSalaire.objects.create(
                    mois=mois_suivant,
                    annee=annee_suivante,
                    ecole=periode.ecole,
                    nombre_semaines=periode.nombre_semaines,  # Reprendre le même nombre de semaines
                    cree_par=request.user
                )
                
                messages.success(
                    request, 
                    f"Période {periode} clôturée avec succès ! "
                    f"Nouvelle période créée automatiquement : {nouvelle_periode}"
                )
            else:
                messages.success(
                    request, 
                    f"Période {periode} clôturée avec succès ! "
                    f"La période suivante existe déjà."
                )
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la clôture : {str(e)}")
    
    return redirect('salaires:gestion_periodes')


@login_required
def changer_statut_enseignant(request, enseignant_id):
    """Changement de statut d'un enseignant"""
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    
    if request.method == 'POST':
        nouveau_statut = request.POST.get('nouveau_statut')
        
        if nouveau_statut in ['ACTIF', 'CONGE', 'SUSPENDU', 'DEMISSIONNAIRE']:
            ancien_statut = enseignant.get_statut_display()
            enseignant.statut = nouveau_statut
            enseignant.save()
            
            nouveau_statut_display = enseignant.get_statut_display()
            messages.success(
                request, 
                f"Le statut de {enseignant.nom_complet} a été changé de '{ancien_statut}' à '{nouveau_statut_display}' avec succès !"
            )
        else:
            messages.error(request, "Statut invalide.")
    else:
        messages.info(request, "Méthode non autorisée pour cette action.")
    
    return redirect('salaires:liste_enseignants')


@login_required
@can_add_teachers
def ajouter_enseignant(request):
    """Ajouter un nouvel enseignant"""
    if request.method == 'POST':
        form = EnseignantForm(request.POST)
        if form.is_valid():
            enseignant = form.save(commit=False)
            enseignant.cree_par = request.user
            enseignant.save()
            
            messages.success(
                request, 
                f"L'enseignant {enseignant.nom_complet} a été ajouté avec succès !"
            )
            return redirect('salaires:detail_enseignant', enseignant_id=enseignant.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = EnseignantForm()
    
    context = {
        'form': form,
        'title': 'Ajouter un Enseignant',
        'submit_text': 'Créer l\'Enseignant',
    }
    
    return render(request, 'salaires/ajouter_enseignant.html', context)


@login_required
def modifier_enseignant(request, enseignant_id):
    """Modifier un enseignant existant"""
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    
    if request.method == 'POST':
        form = EnseignantForm(request.POST, instance=enseignant)
        if form.is_valid():
            form.save()
            messages.success(
                request, 
                f"L'enseignant {enseignant.nom_complet} a été modifié avec succès !"
            )
            return redirect('salaires:detail_enseignant', enseignant_id=enseignant.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = EnseignantForm(instance=enseignant)
    
    context = {
        'form': form,
        'enseignant': enseignant,
        'title': f'Modifier {enseignant.nom_complet}',
        'submit_text': 'Enregistrer les Modifications',
    }
    
    return render(request, 'salaires/ajouter_enseignant.html', context)


@login_required
def supprimer_enseignant(request, enseignant_id):
    """Supprimer un enseignant"""
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    
    if request.method == 'POST':
        # Vérifier s'il y a des états de salaire associés
        etats_count = enseignant.etats_salaire.count()
        affectations_count = enseignant.affectations.count()
        
        if etats_count > 0 or affectations_count > 0:
            messages.warning(
                request, 
                f"Impossible de supprimer {enseignant.nom_complet}. "
                f"Cet enseignant a {etats_count} état(s) de salaire et {affectations_count} affectation(s). "
                f"Vous pouvez le désactiver en changeant son statut."
            )
        else:
            nom_complet = enseignant.nom_complet
            enseignant.delete()
            messages.success(
                request, 
                f"L'enseignant {nom_complet} a été supprimé avec succès."
            )
    
    return redirect('salaires:liste_enseignants')
