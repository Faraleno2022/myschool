from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.db import transaction, IntegrityError
from django.utils import timezone
from decimal import Decimal
from datetime import date, datetime
import os
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import F, ExpressionWrapper, DecimalField, Case, When, Value, Q, Sum, Count
from django.db.models.functions import Coalesce, Least
from django.db.models.functions import Greatest
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side, numbers
from io import BytesIO
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
except Exception:
    canvas = None
    A4 = (595.27, 841.89)
    ImageReader = None
from ecole_moderne.pdf_utils import draw_logo_watermark

from .models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise, Relance, TwilioInboundMessage
from eleves.models import Eleve, GrilleTarifaire, Classe
from .forms import PaiementForm, EcheancierForm, RechercheForm
from .remise_forms import PaiementRemiseForm, CalculateurRemiseForm
from utilisateurs.utils import user_is_admin, filter_by_user_school, user_school
from utilisateurs.permissions import can_add_payments, can_modify_payments, can_delete_payments, can_validate_payments, can_view_reports, can_apply_discounts
from .notifications import (
    send_payment_receipt,
    send_enrollment_confirmation,
    send_relance_notification,
    send_retard_notification,
)

# ... (rest of the code remains the same)

@csrf_exempt
@require_http_methods(["POST"])
def twilio_inbound(request):
    """Réception des messages entrants Twilio (SMS/WhatsApp).
    Journalise les données utiles et répond 200.
    """
    if not _is_valid_twilio_request(request):
        return HttpResponse("Invalid signature", status=403)
    try:
        data = request.POST.dict()
    except Exception:
        data = {}
    # Champs utiles possibles: From, To, Body, SmsSid, MessageSid, WaId, NumMedia, etc.
    logging.getLogger(__name__).info("Twilio inbound message: %s", data)
    # Persist inbound message
    try:
        from_number = (data.get('From') or '').strip()
        to_number = (data.get('To') or '').strip()
        body = data.get('Body')
        message_sid = data.get('MessageSid') or data.get('SmsSid')
        wa_id = data.get('WaId')
        try:
            num_media = int(data.get('NumMedia') or 0)
        except Exception:
            num_media = 0
        channel = 'WHATSAPP' if from_number.lower().startswith('whatsapp:') else 'SMS'
        TwilioInboundMessage.objects.update_or_create(
            message_sid=message_sid,
            defaults={
                'channel': channel,
                'from_number': from_number,
                'to_number': to_number,
                'body': body,
                'wa_id': wa_id,
                'num_media': num_media,
                'raw_data': data,
            }
        )
    except Exception:
        logging.getLogger(__name__).exception("Erreur lors de l'enregistrement du message entrant Twilio")
    return JsonResponse({"status": "ok"})

@csrf_exempt
@require_http_methods(["POST"]) 
def twilio_status_callback(request):
    """Réception des callbacks de statut Twilio (optionnel).
    Journalise l'événement et répond 200.
    """
    if not _is_valid_twilio_request(request):
        return HttpResponse("Invalid signature", status=403)
    try:
        data = request.POST.dict()
    except Exception:
        data = {}
    logging.getLogger(__name__).info("Twilio status callback: %s", data)
    # Persist status update if MessageSid is present
    try:
        message_sid = data.get('MessageSid') or data.get('SmsSid')
        if message_sid:
            status = data.get('MessageStatus') or data.get('SmsStatus')
            error_code = data.get('ErrorCode')
            error_message = data.get('ErrorMessage')
            from django.utils import timezone as _tz
            obj, created = TwilioInboundMessage.objects.get_or_create(message_sid=message_sid, defaults={'raw_data': data})
            obj.delivery_status = status
            obj.error_code = str(error_code) if error_code is not None else obj.error_code
            obj.error_message = error_message or obj.error_message
            obj.status_updated_at = _tz.now()
            # Conserver dernières données brutes utiles
            try:
                merged = obj.raw_data or {}
                merged.update(data)
                obj.raw_data = merged
            except Exception:
                obj.raw_data = data
            obj.save()
    except Exception:
        logging.getLogger(__name__).exception("Erreur lors de l'enregistrement du status callback Twilio")
    return JsonResponse({"status": "ok"})

# ---------------------------------------------------------------
# Tableau de bord Paiements – statistiques réelles + listes
# ---------------------------------------------------------------

def _compute_stats():
    """Calcule les statistiques affichées sur le tableau de bord.
    Retourne un dict: total_paiements_mois, nombre_paiements_mois, eleves_en_retard, paiements_en_attente.
    """
    try:
        from django.utils import timezone as _tz
        today = _tz.localdate() if hasattr(_tz, 'localdate') else date.today()
    except Exception:
        today = date.today()

    # Début du mois courant
    try:
        month_start = today.replace(day=1)
    except Exception:
        # fallback simple
        month_start = date(today.year, today.month, 1)

    # Somme des paiements validés sur le mois (DateField -> filtre inclusif par bornes)
    total_mois = (
        Paiement.objects.filter(
            statut='VALIDE',
            date_paiement__gte=month_start,
            date_paiement__lte=today,
        ).aggregate(total=Sum('montant'))['total'] or 0
    )

    # Nombre de paiements (tous statuts) ce mois
    nb_paiements_mois = Paiement.objects.filter(
        date_paiement__gte=month_start,
        date_paiement__lte=today,
    ).count()

    # Élèves en retard: montants exigibles (échéances dépassées) > payés + remises
    exigible_expr = (
        Case(
            When(date_echeance_inscription__lte=today, then=F('frais_inscription_du')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_1__lte=today, then=F('tranche_1_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_2__lte=today, then=F('tranche_2_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_3__lte=today, then=F('tranche_3_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
    )
    remises_expr = Coalesce(
        Sum('eleve__paiements__remises__montant_remise', filter=Q(eleve__paiements__statut='VALIDE')),
        Value(0),
        output_field=DecimalField(max_digits=10, decimal_places=0),
    )
    # Les remises ne doivent compenser que le montant exigible à date (pas les échéances futures)
    remises_applicables = Least(remises_expr, exigible_expr)
    paye_effectif_expr = (
        F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
        + remises_applicables
    )
    retard_expr = ExpressionWrapper(exigible_expr - paye_effectif_expr, output_field=DecimalField(max_digits=10, decimal_places=0))
    eleves_retard_count = (
        EcheancierPaiement.objects
        .annotate(retard=retard_expr)
        .filter(retard__gt=0)
        .count()
    )

    # Paiements en attente
    en_attente_count = Paiement.objects.filter(statut='EN_ATTENTE').count()

    return {
        'total_paiements_mois': int(total_mois or 0),
        'nombre_paiements_mois': int(nb_paiements_mois or 0),
        'eleves_en_retard': int(eleves_retard_count or 0),
        'paiements_en_attente': int(en_attente_count or 0),
    }


def tableau_bord_paiements(request):
    """Affiche le tableau de bord des paiements avec stats et listes utiles."""
    if not _template_exists('paiements/tableau_bord.html'):
        return HttpResponse('Tableau de bord paiements (template manquant)')

    stats = _compute_stats()

    # Paiements récents: derniers validés d'abord, sinon tout, sur 30 jours sinon fallback 20 derniers
    try:
        from django.utils import timezone as _tz
        today = _tz.localdate() if hasattr(_tz, 'localdate') else date.today()
    except Exception:
        today = date.today()

    try:
        from datetime import timedelta
        last_30 = today - timedelta(days=30)
    except Exception:
        last_30 = today

    paiements_recents_qs = (
        Paiement.objects
        .select_related('eleve', 'type_paiement', 'mode_paiement')
        .filter(date_paiement__gte=last_30)
        .order_by('-date_paiement', '-date_creation')
    )
    if paiements_recents_qs.count() == 0:
        paiements_recents_qs = (
            Paiement.objects
            .select_related('eleve', 'type_paiement', 'mode_paiement')
            .order_by('-date_paiement', '-date_creation')
        )
    paiements_recents = list(paiements_recents_qs[:20])

    # Top élèves en retard (montant de retard décroissant)
    exigible_expr = (
        Case(
            When(date_echeance_inscription__lte=today, then=F('frais_inscription_du')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_1__lte=today, then=F('tranche_1_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_2__lte=today, then=F('tranche_2_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_3__lte=today, then=F('tranche_3_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
    )
    remises_expr = Coalesce(
        Sum('eleve__paiements__remises__montant_remise', filter=Q(eleve__paiements__statut='VALIDE')),
        Value(0),
        output_field=DecimalField(max_digits=10, decimal_places=0),
    )
    # Les remises ne compensent que les montants exigibles au jour J
    remises_applicables = Least(remises_expr, exigible_expr)
    paye_effectif_expr = (
        F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
        + remises_applicables
    )
    retard_expr = ExpressionWrapper(exigible_expr - paye_effectif_expr, output_field=DecimalField(max_digits=10, decimal_places=0))
    eleves_en_retard = (
        EcheancierPaiement.objects
        .select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
        .annotate(retard_db=retard_expr)
        .filter(retard_db__gt=0)
        .order_by('-retard_db')[:10]
    )

    context = {
        'titre_page': 'Tableau de bord des paiements',
        'stats': stats,
        'paiements_recents': paiements_recents,
        'eleves_en_retard': eleves_en_retard,
    }
    return render(request, 'paiements/tableau_bord.html', context)

def liste_paiements(request):
    """Liste des paiements avec recherche, filtres de statut et pagination.
    Paramètres GET:
      - q: texte de recherche (élève: nom/prénom/matricule, reçu, référence, observations)
      - statut: EN_ATTENTE | VALIDE | REJETE | REMBOURSE (optionnel)
      - page: numéro de page
    """
    titre_page = "Liste des paiements"
    q = (request.GET.get('q') or '').strip()
    statut = (request.GET.get('statut') or '').strip()
    page = request.GET.get('page') or 1

    # Base queryset avec relations chargées
    qs = (
        Paiement.objects.select_related('eleve', 'type_paiement', 'mode_paiement')
    )

    # Filtre recherche plein texte simple
    if q:
        qs = qs.filter(
            Q(numero_recu__icontains=q)
            | Q(reference_externe__icontains=q)
            | Q(observations__icontains=q)
            | Q(eleve__nom__icontains=q)
            | Q(eleve__prenom__icontains=q)
            | Q(eleve__matricule__icontains=q)
        )

    # Appliquer filtre par statut (si fourni) pour que les totaux reflètent la liste courante
    if statut:
        qs = qs.filter(statut=statut)

    # Calcul des totaux dynamiques (adaptés aux filtres en place)
    try:
        from django.utils import timezone as _tz
        today = _tz.localdate() if hasattr(_tz, 'localdate') else date.today()
    except Exception:
        today = date.today()
    try:
        month_start = today.replace(day=1)
    except Exception:
        month_start = date(today.year, today.month, 1)

    qs_effectif = qs
    qs_non_annule = qs_effectif.exclude(statut='ANNULE')

    total_paiements = qs_non_annule.count()
    montant_total = int(qs_non_annule.aggregate(total=Sum('montant'))['total'] or 0)

    en_attente_qs = qs_effectif.filter(statut='EN_ATTENTE')
    total_en_attente = en_attente_qs.count()
    montant_en_attente = int(en_attente_qs.aggregate(total=Sum('montant'))['total'] or 0)

    ce_mois_qs = qs_non_annule.filter(date_paiement__gte=month_start, date_paiement__lte=today)
    total_ce_mois = ce_mois_qs.count()
    montant_ce_mois = int(ce_mois_qs.aggregate(total=Sum('montant'))['total'] or 0)

    # Calculs supplémentaires: Dû scolarité net après remises + frais d'inscription fixes (30k/élève)
    eleves_qs = Eleve.objects.all()
    if q:
        eleves_qs = eleves_qs.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(matricule__icontains=q)
            | Q(classe__nom__icontains=q) | Q(classe__ecole__nom__icontains=q)
            | Q(paiements__numero_recu__icontains=q) | Q(paiements__reference_externe__icontains=q)
            | Q(paiements__observations__icontains=q)
        ).distinct()

    eleves_count = eleves_qs.count() if q else Eleve.objects.count()

    eche_qs = EcheancierPaiement.objects.filter(eleve__in=eleves_qs)
    dues_sco_expr = (
        Coalesce(
            F('tranche_1_due'),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=0)),
            output_field=DecimalField(max_digits=12, decimal_places=0),
        )
        + Coalesce(
            F('tranche_2_due'),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=0)),
            output_field=DecimalField(max_digits=12, decimal_places=0),
        )
        + Coalesce(
            F('tranche_3_due'),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=0)),
            output_field=DecimalField(max_digits=12, decimal_places=0),
        )
    )
    remises_expr = Coalesce(
        Sum('eleve__paiements__remises__montant_remise', filter=Q(eleve__paiements__statut='VALIDE')),
        Value(0),
        output_field=DecimalField(max_digits=12, decimal_places=0),
    )
    aggr_du = eche_qs.aggregate(
        dues_sco=Coalesce(
            Sum(dues_sco_expr, output_field=DecimalField(max_digits=12, decimal_places=0)),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=0)),
            output_field=DecimalField(max_digits=12, decimal_places=0),
        ),
        remises=remises_expr,
    )
    dues_sco_total = int(aggr_du.get('dues_sco') or 0)
    remises_total = int(aggr_du.get('remises') or 0)
    du_sco_net = max(dues_sco_total - remises_total, 0)
    frais_inscription_par_eleve = 30000
    frais_inscription_total = eleves_count * frais_inscription_par_eleve
    du_global_net = du_sco_net + frais_inscription_total

    # Détail par école/classe (filtre libre appliqué aux élèves)
    detail_qs = (
        eche_qs
        .values(
            'eleve__classe__ecole__id', 'eleve__classe__ecole__nom',
            'eleve__classe__id', 'eleve__classe__nom'
        )
        .annotate(
            eleves_count=Count('eleve', distinct=True),
            dues_sco_sum=Coalesce(
                Sum(dues_sco_expr, output_field=DecimalField(max_digits=12, decimal_places=0)),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=0)),
                output_field=DecimalField(max_digits=12, decimal_places=0),
            ),
            remises_sum=remises_expr,
        )
        .order_by('eleve__classe__ecole__nom', 'eleve__classe__nom')
    )
    totaux_du_detail_classes = []
    for row in detail_qs:
        dues = int(row.get('dues_sco_sum') or 0)
        rem = int(row.get('remises_sum') or 0)
        net_sco = max(dues - rem, 0)
        cnt = int(row.get('eleves_count') or 0)
        insc = cnt * frais_inscription_par_eleve
        tot = net_sco + insc
        totaux_du_detail_classes.append({
            'ecole_id': row.get('eleve__classe__ecole__id'),
            'ecole_nom': row.get('eleve__classe__ecole__nom'),
            'classe_id': row.get('eleve__classe__id'),
            'classe_nom': row.get('eleve__classe__nom'),
            'eleves_count': cnt,
            'du_sco_net': net_sco,
            'frais_inscription_total': insc,
            'du_global_net': tot,
        })

    # Pagination
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)

    context = {
        'titre_page': titre_page,
        'q': q,
        'statut': statut,
        'paiements': page_obj.object_list,
        'page_obj': page_obj,
        # Totaux pour l'UI (utilisés par _paiements_resultats.html)
        'totaux': {
            'total_paiements': int(total_paiements or 0),
            'montant_total': int(montant_total or 0),
            'total_en_attente': int(total_en_attente or 0),
            'montant_en_attente': int(montant_en_attente or 0),
            'total_ce_mois': int(total_ce_mois or 0),
            'montant_ce_mois': int(montant_ce_mois or 0),
        },
        'totaux_du': {
            'eleves_count': int(eleves_count or 0),
            'du_sco_net': int(du_sco_net or 0),
            'frais_inscription_total': int(frais_inscription_total or 0),
            'du_global_net': int(du_global_net or 0),
            'frais_inscription_unitaire': int(frais_inscription_par_eleve),
        },
        'totaux_du_detail_classes': totaux_du_detail_classes,
        # Alerte relance en haut du fragment (compte global des élèves en retard)
        'eleves_en_retard': _compute_stats().get('eleves_en_retard', 0),
    }

    # Réponse partielle pour les requêtes AJAX (utilisé par la recherche/pagination dynamique)
    try:
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    except Exception:
        is_ajax = False
    if is_ajax and _template_exists('paiements/_paiements_resultats.html'):
        return render(request, 'paiements/_paiements_resultats.html', context)

    template = 'paiements/liste_paiements.html' if _template_exists('paiements/liste_paiements.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Liste des paiements')

def detail_paiement(request, paiement_id:int):
    """Affiche le détail d'un paiement.

    Contexte pour `templates/paiements/detail_paiement.html`:
      - titre_page: str
      - paiement: instance `Paiement`
      - is_admin: bool
      - user_permissions: dict avec `can_validate_payments`
    """
    paiement = get_object_or_404(
        Paiement.objects.select_related(
            'eleve', 'type_paiement', 'mode_paiement',
            'eleve__classe', 'eleve__classe__ecole',
        ),
        pk=paiement_id,
    )

    # Préparer les informations de permissions utilisées dans le template
    perms_ctx = {
        'can_validate_payments': can_validate_payments(request.user) if request.user.is_authenticated else False,
    }

    # Total des remises appliquées sur ce paiement
    try:
        remises_total = (
            paiement.remises.aggregate(total=Sum('montant_remise')).get('total') or 0
        )
    except Exception:
        remises_total = 0

    context = {
        'titre_page': f"Détail du paiement #{paiement.id}",
        'paiement': paiement,
        'is_admin': user_is_admin(request.user) if request.user.is_authenticated else False,
        'user_permissions': perms_ctx,
        'remises_total': int(remises_total or 0),
    }
    return render(request, 'paiements/detail_paiement.html', context)

def ajouter_paiement(request, eleve_id:int=None):
    """Créer un paiement.
    - GET: affiche le formulaire `templates/paiements/form_paiement.html`
    - POST: enregistre le paiement en statut EN_ATTENTE
    """
    titre_page = "Ajouter un paiement"
    action = "Enregistrer"

    eleve = None
    initial = {}
    if eleve_id:
        eleve = get_object_or_404(Eleve.objects.select_related('classe', 'classe__ecole'), pk=eleve_id)
        initial['eleve'] = eleve

    if request.method == 'POST':
        form = PaiementForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                paiement: Paiement = form.save(commit=False)
                # Attacher l'utilisateur créateur si connecté
                if request.user.is_authenticated:
                    paiement.cree_par = request.user
                # Statut par défaut reste EN_ATTENTE (défini dans le modèle)
                paiement.save()
            # Notifications: reçu paiement (WhatsApp + SMS) et, si inscription, confirmation d'inscription
            try:
                send_payment_receipt(paiement.eleve, paiement)
                type_nom = (getattr(paiement.type_paiement, 'nom', '') or '').strip().lower()
                if 'inscription' in type_nom:
                    send_enrollment_confirmation(paiement.eleve, paiement)
            except Exception:
                logging.getLogger(__name__).exception("Erreur lors de l'envoi des notifications Twilio")
            messages.success(request, "Paiement enregistré avec succès. Étape suivante: création de l'échéancier.")
            try:
                # Rediriger vers la création d'échéancier pour l'élève concerné
                return redirect('paiements:creer_echeancier', eleve_id=paiement.eleve_id)
            except Exception:
                # Fallback: page d'échéancier de l'élève
                return redirect('paiements:echeancier_eleve', eleve_id=paiement.eleve_id)
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = PaiementForm(initial=initial)
        # Si l'élève est imposé, fixer la valeur initiale proprement
        if eleve:
            form.fields['eleve'].initial = eleve

    context = {
        'titre_page': titre_page,
        'action': action,
        'form': form,
        'eleve': eleve,
    }
    return render(request, 'paiements/form_paiement.html', context)

def valider_paiement(request, paiement_id:int):
    """Valide un paiement en le passant au statut VALIDE.

    - Vérifie les permissions: admin ou can_validate_payments
    - Met à jour: statut, date_validation, valide_par, date_modification
    - Optionnel: tente d'allouer le paiement à l'échéancier si une fonction utilitaire existe
    - Notifie le responsable (WhatsApp/SMS) avec le reçu
    """
    paiement = get_object_or_404(Paiement, pk=paiement_id)

    if not request.user.is_authenticated or not (user_is_admin(request.user) or can_validate_payments(request.user)):
        messages.error(request, "Vous n'avez pas l'autorisation de valider ce paiement.")
        return redirect('paiements:detail_paiement', paiement_id=paiement.id)

    if paiement.statut == 'VALIDE':
        messages.info(request, "Ce paiement est déjà validé.")
        return redirect('paiements:detail_paiement', paiement_id=paiement.id)

    with transaction.atomic():
        paiement.statut = 'VALIDE'
        try:
            paiement.date_validation = timezone.now()
        except Exception:
            from django.utils import timezone as _tz
            paiement.date_validation = _tz.now()
        paiement.valide_par = request.user
        try:
            paiement.date_modification = timezone.now()
        except Exception:
            pass
        paiement.save()

        # Tenter l'allocation à l'échéancier si une fonction utilitaire existe
        try:
            _allocate_payment_to_echeancier  # type: ignore[name-defined]
        except NameError:
            _allocate_payment_to_echeancier = None  # type: ignore[assignment]
        try:
            if _allocate_payment_to_echeancier:
                _allocate_payment_to_echeancier(paiement)  # type: ignore[misc]
        except Exception:
            logging.getLogger(__name__).exception("Erreur lors de l'allocation du paiement à l'échéancier")

    # Envoyer le reçu de paiement après validation
    try:
        send_payment_receipt(paiement.eleve, paiement)
    except Exception:
        logging.getLogger(__name__).exception("Erreur lors de l'envoi du reçu après validation")

    messages.success(request, "Paiement validé avec succès.")
    return redirect('paiements:detail_paiement', paiement_id=paiement.id)

def relancer_eleve(request, eleve_id:int):
    """Crée une relance et envoie la notification (WhatsApp/SMS) au responsable.
    GET params optionnels:
      - canal: SMS | WHATSAPP (par défaut WHATSAPP)
      - message: texte personnalisé
    """
    eleve = get_object_or_404(Eleve.objects.select_related('classe'), pk=eleve_id)
    canal = (request.GET.get('canal') or 'WHATSAPP').upper()
    message_txt = (request.GET.get('message') or '').strip()

    # Solde estimé depuis l'échéancier
    try:
        echeancier = getattr(eleve, 'echeancier', None)
        solde_estime = echeancier.solde_restant if echeancier else 0
    except Exception:
        solde_estime = 0

    if not message_txt:
        message_txt = (
            f"Merci de régulariser les frais de scolarité. Élève: {eleve.nom_complet} ({eleve.matricule})."
        )

    with transaction.atomic():
        relance = Relance.objects.create(
            eleve=eleve,
            canal=canal if canal in {c for c, _ in Relance.CANAL_CHOICES} else 'AUTRE',
            message=message_txt,
            statut='ENREGISTREE',
            solde_estime=solde_estime or 0,
            cree_par=request.user if request.user.is_authenticated else None,
        )
    try:
        send_relance_notification(relance)
        messages.success(request, "Relance créée et notification envoyée.")
    except Exception:
        logging.getLogger(__name__).exception("Erreur lors de l'envoi de la relance Twilio")
        messages.warning(request, "Relance créée mais l'envoi de la notification a échoué.")

    # Redirection: détail élève si dispo, sinon liste paiements
    try:
        return redirect('eleves:detail', eleve_id=eleve.id)
    except Exception:
        return redirect('paiements:liste_paiements')

def envoyer_notifs_retards(request):
    """Envoie des notifications de retard aux responsables des élèves avec solde > 0.
    Action manuelle: GET uniquement, simple résumé via messages.
    """
    if not request.user.is_authenticated:
        return HttpResponse(status=403)
    # Optionnel: restreindre aux admins/permissions
    if not (user_is_admin(request.user) or can_view_reports(request.user)):
        return HttpResponse(status=403)

    # Annoter montant de retard au niveau DB: (exigible - (payé + remises))
    try:
        from django.utils import timezone as _tz
        today = _tz.localdate() if hasattr(_tz, 'localdate') else date.today()
    except Exception:
        today = date.today()

    exigible_expr = (
        Case(
            When(date_echeance_inscription__lte=today, then=F('frais_inscription_du')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_1__lte=today, then=F('tranche_1_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_2__lte=today, then=F('tranche_2_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
        + Case(
            When(date_echeance_tranche_3__lte=today, then=F('tranche_3_due')),
            default=Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=0),
        )
    )
    remises_expr = Coalesce(
        Sum('eleve__paiements__remises__montant_remise', filter=Q(eleve__paiements__statut='VALIDE')),
        Value(0),
        output_field=DecimalField(max_digits=10, decimal_places=0),
    )
    # Limiter l'effet des remises au montant actuellement exigible
    remises_applicables = Least(remises_expr, exigible_expr)
    paye_effectif_expr = (
        F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
        + remises_applicables
    )
    retard_expr = ExpressionWrapper(exigible_expr - paye_effectif_expr, output_field=DecimalField(max_digits=10, decimal_places=0))
    qs = (
        EcheancierPaiement.objects.select_related('eleve', 'eleve__classe')
        .annotate(retard=retard_expr)
        .filter(retard__gt=0)
    )
    envoyes = 0
    for ech in qs[:500]:  # sécurité: batch max 500
        try:
            send_retard_notification(ech.eleve, ech.retard)
            envoyes += 1
        except Exception:
            logging.getLogger(__name__).exception("Échec envoi retard pour %s", getattr(ech.eleve, 'nom_complet', 'eleve'))
            continue
    messages.info(request, f"Notifications de retard envoyées: {envoyes} (sur {qs.count()} éligibles)")
    # Rediriger vers relances ou tableau de bord
    return redirect('paiements:liste_relances')

def liste_relances(request):
    """Liste des relances avec filtres et pagination."""
    titre_page = "Liste des relances"
    q = (request.GET.get('q') or '').strip()
    canal = (request.GET.get('canal') or '').strip().upper()
    statut = (request.GET.get('statut') or '').strip().upper()

    qs = (
        Relance.objects.select_related('eleve', 'eleve__classe')
        .order_by('-date_creation')
    )
    if q:
        qs = qs.filter(
            Q(eleve__nom__icontains=q)
            | Q(eleve__prenom__icontains=q)
            | Q(eleve__matricule__icontains=q)
            | Q(message__icontains=q)
        )
    if canal:
        qs = qs.filter(canal=canal)
    if statut:
        qs = qs.filter(statut=statut)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    context = {
        'titre_page': titre_page,
        'q': q,
        'canal': canal,
        'statut': statut,
        'page_obj': page_obj,
    }
    template = 'paiements/relances.html' if _template_exists('paiements/relances.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Liste des relances')

def echeancier_eleve(request, eleve_id:int):
    """Affiche l'échéancier et l'historique des paiements d'un élève.

    Contexte fourni au template `templates/paiements/echeancier_eleve.html`:
      - titre_page: Titre de la page
      - eleve: instance d'`Eleve`
      - echeancier: instance d'`EcheancierPaiement` (ou None si non créé)
      - paiements: queryset des `Paiement` liés à l'élève (ordonnés récents d'abord)
      - today: date du jour (timezone-aware localdate si dispo)
    """
    # Récupération de l'élève avec sa classe/école pour l'en-tête
    eleve = get_object_or_404(Eleve.objects.select_related('classe', 'classe__ecole'), pk=eleve_id)

    # Échéancier (peut ne pas exister encore)
    try:
        echeancier = getattr(eleve, 'echeancier', None)
    except Exception:
        echeancier = None

    # Historique des paiements (les plus récents d'abord)
    paiements = (
        Paiement.objects
        .select_related('type_paiement', 'mode_paiement')
        .filter(eleve=eleve)
        .order_by('-date_paiement', '-date_creation')
    )

    # Date du jour pour l'affichage des retards
    try:
        from django.utils import timezone as _tz
        today = _tz.localdate() if hasattr(_tz, 'localdate') else date.today()
    except Exception:
        today = date.today()

    context = {
        'titre_page': "Échéancier des paiements",
        'eleve': eleve,
        'echeancier': echeancier,
        'paiements': paiements,
        'today': today,
    }
    return render(request, 'paiements/echeancier_eleve.html', context)

def creer_echeancier(request, eleve_id:int):
    """Créer ou éditer l'échéancier d'un élève.

    - Si un échéancier existe déjà: redirige vers la page d'échéancier avec message.
    - GET: affiche `templates/paiements/form_echeancier.html` pré-rempli si possible par la grille tarifaire.
    - POST: valide et enregistre l'échéancier puis redirige vers la page d'échéancier de l'élève.
    """
    eleve = get_object_or_404(Eleve.objects.select_related('classe', 'classe__ecole'), pk=eleve_id)

    # Si un échéancier existe déjà, on informe et on redirige
    try:
        if getattr(eleve, 'echeancier', None):
            messages.info(request, "Un échéancier existe déjà pour cet élève.")
            return redirect('paiements:echeancier_eleve', eleve_id=eleve.id)
    except Exception:
        pass

    # Pré-remplissage depuis la grille tarifaire si disponible
    initial = {}
    try:
        niveau = getattr(eleve.classe, 'niveau', None)
        ecole = getattr(eleve.classe, 'ecole', None)
        # Année scolaire préférée: celle de la classe de l'élève, sinon calcul par date
        today = date.today()
        annee_scolaire_def = f"{today.year}-{today.year+1}" if today.month >= 9 else f"{today.year-1}-{today.year}"
        annee_classe = getattr(eleve.classe, 'annee_scolaire', None)
        from eleves.models import GrilleTarifaire as _Grille
        grille = None
        # 1) Essayer l'année de la classe si présente
        if annee_classe:
            grille = _Grille.objects.filter(ecole=ecole, niveau=niveau, annee_scolaire=annee_classe).first()
            if grille is None:
                messages.info(request, f"Aucune grille trouvée pour l'année {annee_classe}. Recherche d'une autre année...")
        # 2) Sinon essayer l'année par défaut calculée (ou si 1) a échoué et diffère)
        if grille is None:
            if not annee_classe or (annee_classe and annee_classe != annee_scolaire_def):
                grille = _Grille.objects.filter(ecole=ecole, niveau=niveau, annee_scolaire=annee_scolaire_def).first()
                if grille and annee_classe and annee_classe != annee_scolaire_def:
                    messages.info(request, f"Utilisation de la grille {grille.annee_scolaire} (aucune pour {annee_classe}).")
        # 3) Fallback: prendre la plus récente disponible pour l'école/niveau
        if grille is None:
            grille = _Grille.objects.filter(ecole=ecole, niveau=niveau).order_by('-annee_scolaire').first()
            if grille:
                messages.warning(request, f"Grille exacte introuvable. Utilisation de la plus récente: {grille.annee_scolaire}.")

        if grille:
            initial.update({
                'annee_scolaire': grille.annee_scolaire,
                'frais_inscription_du': grille.frais_inscription,
                'tranche_1_due': grille.tranche_1,
                'tranche_2_due': grille.tranche_2,
                'tranche_3_due': grille.tranche_3,
            })
        # Proposer des dates d'échéance par défaut
        try:
            # Inscription: aujourd'hui, puis jalons (janvier/mars) pour les tranches
            from datetime import date as _d
            today_d = _d.today()
            initial.setdefault('date_echeance_inscription', today_d)
            # 15 janvier, 15 mars, 15 mai de l'année de fin de l'année scolaire (annee_debut + 1)
            annee_scol = (initial.get('annee_scolaire') or annee_scolaire_def)
            try:
                annee_debut = int(str(annee_scol).split('-')[0])
            except Exception:
                annee_debut = today_d.year
            annee_fin = annee_debut + 1
            initial.setdefault('date_echeance_tranche_1', _d(annee_fin, 1, 15))
            initial.setdefault('date_echeance_tranche_2', _d(annee_fin, 3, 15))
            # Dernière tranche: 15 mai
            initial.setdefault('date_echeance_tranche_3', _d(annee_fin, 5, 15))
        except Exception:
            pass
    except Exception:
        grille = None

    if request.method == 'POST':
        form = EcheancierForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ech: EcheancierPaiement = form.save(commit=False)
                ech.eleve = eleve
                if request.user.is_authenticated:
                    ech.cree_par = request.user
                ech.save()
            messages.success(request, "Échéancier créé avec succès.")
            return redirect('paiements:echeancier_eleve', eleve_id=eleve.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = EcheancierForm(initial=initial)

    context = {
        'titre_page': "Créer un échéancier",
        'eleve': eleve,
        'form': form,
        'grille': grille if 'grille' in locals() else None,
        'action': 'Créer',
    }
    return render(request, 'paiements/form_echeancier.html', context)

def generer_recu_pdf(request, paiement_id:int):
    """Génère un reçu PDF téléchargeable pour un paiement validé.

    - Ajoute un filigrane via `ecole_moderne/pdf_utils.draw_logo_watermark`
    - Inclut les informations clés du paiement et de l'élève
    - Liste les remises appliquées et affiche le total des remises
    """
    paiement = get_object_or_404(
        Paiement.objects.select_related('eleve', 'type_paiement', 'mode_paiement', 'eleve__classe', 'eleve__classe__ecole'),
        pk=paiement_id,
    )

    # Optionnel: n'autoriser le reçu que pour les paiements validés
    if getattr(paiement, 'statut', 'EN_ATTENTE') != 'VALIDE':
        messages.warning(request, "Le reçu n'est disponible que pour les paiements validés.")
        return redirect('paiements:detail_paiement', paiement_id=paiement.id)

    if canvas is None:
        return HttpResponse("La génération de PDF n'est pas disponible sur ce serveur (ReportLab manquant).", status=500)

    # Calcul total remises
    remises_total = paiement.remises.aggregate(total=Sum('montant_remise')).get('total') or 0

    # Préparer le buffer et le canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Filigrane (désactivé par défaut; activer avec ?wm=1)
    try:
        if (request.GET.get('wm') or '').strip() == '1':
            draw_logo_watermark(c, width, height, opacity=0.05, rotate=30, scale=1.2)
    except Exception:
        pass

    # Mise en page simple
    left = 40
    top = height - 40
    line_h = 18

    def draw_line(text, x=left, y=None, bold=False):
        nonlocal top
        if y is None:
            y = top
        font_name = 'Helvetica-Bold' if bold else 'Helvetica'
        c.setFont(font_name, 11)
        c.drawString(x, y, text)
        top = y - line_h

    # En-tête
    c.setFont('Helvetica-Bold', 16)
    c.drawString(left, top, "Reçu de paiement")
    top -= 10
    c.setFont('Helvetica', 10)
    c.drawString(left, top, (paiement.eleve.classe.ecole.nom if getattr(paiement.eleve.classe, 'ecole', None) else ""))
    top -= 20

    # Photo élève (en haut à droite si disponible) ou placeholder avec initiales si absente
    try:
        img_drawn = False
        img_w, img_h = 100, 100
        x_img = width - 40 - img_w
        y_img = height - 40 - img_h
        if ImageReader is not None:
            photo_path = getattr(getattr(paiement.eleve, 'photo', None), 'path', None)
            if photo_path and os.path.exists(photo_path):
                try:
                    img = ImageReader(photo_path)
                    c.drawImage(img, x_img, y_img, width=img_w, height=img_h, preserveAspectRatio=True, mask='auto')
                    img_drawn = True
                except Exception:
                    img_drawn = False
        if not img_drawn:
            # Dessiner un placeholder avec initiales
            nom_complet = str(getattr(paiement.eleve, 'nom_complet', '') or '').strip()
            initiales = ''.join([p[0].upper() for p in nom_complet.split()[:2]]) or 'E'
            c.setLineWidth(1)
            try:
                c.roundRect(x_img, y_img, img_w, img_h, 8)
            except Exception:
                c.rect(x_img, y_img, img_w, img_h)
            c.setFont('Helvetica-Bold', 24)
            c.drawCentredString(x_img + img_w/2, y_img + img_h/2 - 8, initiales)
            c.setFont('Helvetica', 8)
            c.drawCentredString(x_img + img_w/2, y_img + 6, "Pas de photo")
        # Afficher le nom de l'élève sous l'image/placeholder
        try:
            nom_aff = str(getattr(paiement.eleve, 'nom_complet', '') or '').strip()
            if nom_aff:
                c.setFont('Helvetica', 9)
                c.drawCentredString(x_img + img_w/2, y_img - 12, nom_aff)
        except Exception:
            pass
    except Exception:
        pass

    # Informations paiement
    draw_line(f"Numéro de reçu : {paiement.numero_recu}", bold=True)
    draw_line(f"Date de paiement : {paiement.date_paiement.strftime('%d/%m/%Y')}")
    draw_line(f"Type de paiement : {paiement.type_paiement.nom}")
    draw_line(f"Mode de paiement : {paiement.mode_paiement.nom}")
    if getattr(paiement, 'reference_externe', None):
        draw_line(f"Référence externe : {paiement.reference_externe}")
    if getattr(paiement, 'observations', None):
        # Limiter l'observation à une ligne raisonnable pour le reçu
        obs = str(paiement.observations).strip()
        if obs:
            draw_line(f"Observations : {obs}")
    draw_line(f"Montant : {str(f'{paiement.montant:,.0f}').replace(',', ' ')} GNF", bold=True)

    if remises_total and int(remises_total) > 0:
        draw_line(f"Total remises : -{str(f'{int(remises_total):,}').replace(',', ' ')} GNF")
    # Montant net (jamais négatif)
    montant_net = max(0, int(paiement.montant - (remises_total or 0)))
    draw_line(f"Montant net à payer : {str(f'{montant_net:,}').replace(',', ' ')} GNF", bold=True)

    # Élève
    top -= 6
    draw_line("Informations de l'élève", bold=True)
    draw_line(f"Nom : {paiement.eleve.nom_complet}")
    if getattr(paiement.eleve, 'matricule', None):
        draw_line(f"Matricule : {paiement.eleve.matricule}")
    if getattr(paiement.eleve, 'classe', None):
        draw_line(f"Classe : {paiement.eleve.classe}")

    # Échéances (si disponibles sur l'échéancier de l'élève)
    try:
        echeancier = getattr(paiement.eleve, 'echeancier', None)
    except Exception:
        echeancier = None
    if echeancier:
        top -= 6
        draw_line("Échéances", bold=True)
        try:
            def _fmt_amount(v):
                try:
                    return str(f"{int(v or 0):,}").replace(',', ' ')
                except Exception:
                    return str(v or 0)
            def _fmt_date(d):
                try:
                    return d.strftime('%d/%m/%Y') if d else ''
                except Exception:
                    return str(d) if d else ''
            # Inscription
            draw_line(f"Inscription: {_fmt_amount(echeancier.frais_inscription_du)} GNF - Échéance: {_fmt_date(echeancier.date_echeance_inscription)}")
            # Tranches
            draw_line(f"1ère tranche: {_fmt_amount(echeancier.tranche_1_due)} GNF - Échéance: {_fmt_date(echeancier.date_echeance_tranche_1)}")
            draw_line(f"2ème tranche: {_fmt_amount(echeancier.tranche_2_due)} GNF - Échéance: {_fmt_date(echeancier.date_echeance_tranche_2)}")
            draw_line(f"3ème tranche: {_fmt_amount(echeancier.tranche_3_due)} GNF - Échéance: {_fmt_date(echeancier.date_echeance_tranche_3)}")
        except Exception:
            pass

        # Restes à payer par tranche
        try:
            def _reste(due, paye):
                try:
                    return max(0, int((due or 0) - (paye or 0)))
                except Exception:
                    return 0
            # Calcul global basé sur les paiements validés: somme(montants) - somme(remises)
            try:
                total_du = int((echeancier.frais_inscription_du or 0) + (echeancier.tranche_1_due or 0) + (echeancier.tranche_2_due or 0) + (echeancier.tranche_3_due or 0))
            except Exception:
                total_du = 0

            try:
                aggs = (
                    Paiement.objects
                    .filter(eleve=paiement.eleve, statut='VALIDE')
                    .aggregate(sum_montant=Sum('montant'), sum_remises=Sum('remises__montant_remise'))
                )
                sum_montant = int(aggs.get('sum_montant') or 0)
                sum_remises = int(aggs.get('sum_remises') or 0)
            except Exception:
                sum_montant = 0
                sum_remises = 0

            # Calcul de la couverture: montants payés + remises validées (les remises couvrent une partie du dû)
            couverture_validee = max(0, int(sum_montant) + int(sum_remises))
            # Inclure le paiement courant s'il n'est pas encore validé (montant + remises sur ce reçu)
            try:
                couverture_courante = max(0, int(paiement.montant) + int(remises_total or 0))
            except Exception:
                couverture_courante = 0
            couverture_effective = couverture_validee + (couverture_courante if paiement.statut != 'VALIDE' else 0)
            tout_solde = (total_du <= couverture_effective)
            solde_global = max(0, int(total_du - couverture_effective))

            top -= 6
            # Solde global restant
            draw_line(f"Solde global restant : {str(f'{solde_global:,}').replace(',', ' ')} GNF", bold=True)
            draw_line("Restes à payer par tranche", bold=True)
            if tout_solde:
                r_insc = r_t1 = r_t2 = r_t3 = 0
            else:
                r_insc = _reste(echeancier.frais_inscription_du, echeancier.frais_inscription_paye)
                r_t1 = _reste(echeancier.tranche_1_due, echeancier.tranche_1_payee)
                r_t2 = _reste(echeancier.tranche_2_due, echeancier.tranche_2_payee)
                r_t3 = _reste(echeancier.tranche_3_due, echeancier.tranche_3_payee)
            draw_line(f"Inscription: {str(f'{r_insc:,}').replace(',', ' ')} GNF")
            draw_line(f"1ère tranche: {str(f'{r_t1:,}').replace(',', ' ')} GNF")
            draw_line(f"2ème tranche: {str(f'{r_t2:,}').replace(',', ' ')} GNF")
            draw_line(f"3ème tranche: {str(f'{r_t3:,}').replace(',', ' ')} GNF")
        except Exception:
            pass

    # Remises détaillées
    if remises_total and int(remises_total) > 0:
        top -= 6
        draw_line("Remises appliquées", bold=True)
        for pr in paiement.remises.select_related('remise').all():
            nom = getattr(pr.remise, 'nom', 'Remise')
            montant = str(f"{int(pr.montant_remise):,}").replace(',', ' ')
            draw_line(f"- {nom} : -{montant} GNF")

    # Bloc signatures
    top -= 20
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left, top, "Signatures")
    top -= 16
    # Lignes de signature (caissier et responsable)
    sig_line_y = top
    c.setLineWidth(0.8)
    # Caissier à gauche
    c.line(left, sig_line_y, left + 200, sig_line_y)
    c.setFont('Helvetica', 10)
    c.drawString(left, sig_line_y - 14, "Caissier(e)")
    # Responsable à droite
    right_x = left + 260
    c.setLineWidth(0.8)
    c.line(right_x, sig_line_y, right_x + 200, sig_line_y)
    c.setFont('Helvetica', 10)
    c.drawString(right_x, sig_line_y - 14, "Responsable")

    # Pied de page
    c.setFont('Helvetica', 9)
    c.drawRightString(width - 40, 30, f"Généré le {timezone.now().strftime('%d/%m/%Y %H:%M')}")

    c.showPage()
    c.save()

    pdf = buffer.getvalue()
    buffer.close()

    filename = f"Recu_{paiement.numero_recu}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def export_liste_paiements_excel(request):
    """Exporte en Excel la liste des paiements selon les filtres (q, statut).
    Colonnes: Élève, Classe, École, Type, Montant, Mode, Date, Statut, N° Reçu, Observations
    """
    q = (request.GET.get('q') or '').strip()
    statut = (request.GET.get('statut') or '').strip()

    # Construire le queryset cohérent avec la liste
    qs = (
        Paiement.objects
        .select_related('eleve', 'eleve__classe', 'eleve__classe__ecole', 'type_paiement', 'mode_paiement')
        .exclude(statut='ANNULE')
        .order_by('-date_paiement', '-date_creation')
    )
    if q:
        qs = qs.filter(
            Q(numero_recu__icontains=q)
            | Q(reference_externe__icontains=q)
            | Q(observations__icontains=q)
            | Q(eleve__nom__icontains=q)
            | Q(eleve__prenom__icontains=q)
            | Q(eleve__matricule__icontains=q)
        )
    if statut:
        qs = qs.filter(statut=statut)

    # Créer le classeur
    wb = Workbook()
    ws = wb.active
    ws.title = 'Paiements'

    headers = [
        'Élève', 'Classe', 'École', 'Type', 'Montant (GNF)', 'Mode', 'Date', 'Statut', 'N° Reçu', 'Observations'
    ]
    ws.append(headers)

    # Styles
    header_fill = PatternFill(start_color='007bff', end_color='007bff', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    thin = Side(style='thin', color='DDDDDD')
    border_all = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col_idx)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border_all

    # Lignes
    row_idx = 2
    for p in qs.iterator():
        eleve_nom = f"{getattr(p.eleve, 'nom', '')} {getattr(p.eleve, 'prenom', '')}".strip()
        classe_nom = getattr(getattr(p.eleve, 'classe', None), 'nom', '')
        ecole_nom = getattr(getattr(getattr(p.eleve, 'classe', None), 'ecole', None), 'nom', '')
        type_nom = getattr(p.type_paiement, 'nom', '')
        mode_nom = getattr(p.mode_paiement, 'nom', '')
        date_val = getattr(p, 'date_paiement', None)
        statut_txt = getattr(p, 'statut', '')
        recu = getattr(p, 'numero_recu', '')
        obs = getattr(p, 'observations', '') or ''

        ws.cell(row=row_idx, column=1, value=eleve_nom)
        ws.cell(row=row_idx, column=2, value=classe_nom)
        ws.cell(row=row_idx, column=3, value=ecole_nom)

        ws.cell(row=row_idx, column=4, value=type_nom)
        montant_cell = ws.cell(row=row_idx, column=5, value=float(p.montant or 0))
        montant_cell.number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
        ws.cell(row=row_idx, column=6, value=mode_nom)

        date_cell = ws.cell(row=row_idx, column=7, value=date_val)
        date_cell.number_format = 'DD/MM/YYYY'
        ws.cell(row=row_idx, column=8, value=statut_txt)
        ws.cell(row=row_idx, column=9, value=recu)
        ws.cell(row=row_idx, column=10, value=obs)

        for col in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=col).border = border_all
            if col in (1, 2, 3, 4, 6, 8, 9, 10):
                ws.cell(row=row_idx, column=col).alignment = Alignment(vertical='top')

        row_idx += 1

    # Ajustement des largeurs de colonnes
    widths = [22, 14, 18, 18, 16, 14, 12, 12, 12, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Ligne de total montant
    if row_idx > 2:
        total_label_cell = ws.cell(row=row_idx, column=4, value='Total:')
        total_label_cell.font = Font(bold=True)
        total_cell = ws.cell(row=row_idx, column=5, value=f"=SUM(E2:E{row_idx-1})")
        total_cell.number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
        total_cell.font = Font(bold=True)

    # Réponse HTTP
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"paiements_{ts}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response

def rapport_remises(request):
    """Rapport des remises avec agrégations par élève et filtres période/recherche.

    Contexte pour `templates/paiements/rapport_remises.html`:
      - rows: liste de dicts avec paiements/élève et champs: nb_remises, total_remise
      - total_global: somme de toutes les remises listées
      - q, date_debut, date_fin: filtres saisis
    """
    titre_page = "Rapport des remises"
    q = (request.GET.get('q') or '').strip()
    date_debut = (request.GET.get('date_debut') or '').strip()
    date_fin = (request.GET.get('date_fin') or '').strip()

    # Base queryset sur les remises liées à des paiements validés
    rem_qs = PaiementRemise.objects.select_related('paiement', 'paiement__eleve')
    rem_qs = rem_qs.filter(paiement__statut='VALIDE')

    # Filtre période sur la date du paiement si fournie
    try:
        if date_debut:
            rem_qs = rem_qs.filter(paiement__date_paiement__gte=date_debut)
        if date_fin:
            rem_qs = rem_qs.filter(paiement__date_paiement__lte=date_fin)
    except Exception:
        # En cas de format invalide, ignorer silencieusement
        pass

    # Filtre recherche simple sur élève
    if q:
        rem_qs = rem_qs.filter(
            Q(paiement__eleve__nom__icontains=q)
            | Q(paiement__eleve__prenom__icontains=q)
            | Q(paiement__eleve__matricule__icontains=q)
            | Q(paiement__eleve__classe__nom__icontains=q)
        )

    # Agrégations par élève
    rows = (
        rem_qs
        .values(
            'paiement__eleve__id',
            'paiement__eleve__prenom',
            'paiement__eleve__nom',
            'paiement__eleve__matricule',
            'paiement__eleve__classe__nom',
        )
        .annotate(
            nb_remises=Count('id'),
            total_remise=Coalesce(Sum('montant_remise'), Value(0, output_field=DecimalField(max_digits=10, decimal_places=0)))
        )
        .order_by('-total_remise')
    )

    total_global = 0
    try:
        total_global = int(rem_qs.aggregate(s=Coalesce(Sum('montant_remise'), Value(0)))['s'] or 0)
    except Exception:
        total_global = 0

    context = {
        'titre_page': titre_page,
        'q': q,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'rows': rows,
        'total_global': total_global,
    }
    template = 'paiements/rapport_remises.html' if _template_exists('paiements/rapport_remises.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Rapport remises')

def liste_eleves_soldes(request):
    """Liste des élèves soldés en tenant compte des remises (hors frais d'inscription).

    Règles:
    - Frais d'inscription (30 000 GNF) non impactés par les remises.
    - Remises s'appliquent uniquement à la scolarité (tranches 1..3).
    - Élève considéré soldé si: net_du = inscription_du + max(tranches_du - remises_totales, 0) est payé.
    """
    from django.utils import timezone as _tz
    today = _tz.localdate() if hasattr(_tz, 'localdate') else date.today()

    annee = (request.GET.get('annee') or f"{today.year}-{today.year+1}").strip()
    ecole_id = (request.GET.get('ecole_id') or '').strip()
    classe_id = (request.GET.get('classe_id') or '').strip()
    q = (request.GET.get('q') or '').strip()

    # Base queryset
    qs = (
        EcheancierPaiement.objects
        .select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
    )

    # Filtres école/classe
    if ecole_id:
        qs = qs.filter(eleve__classe__ecole_id=ecole_id)
    if classe_id:
        qs = qs.filter(eleve__classe_id=classe_id)
    if q:
        qs = qs.filter(
            Q(eleve__nom__icontains=q) | Q(eleve__prenom__icontains=q) | Q(eleve__matricule__icontains=q)
        )

    # Expressions de calcul
    dues_sco = (
        Coalesce(F('tranche_1_due'), Value(0))
        + Coalesce(F('tranche_2_due'), Value(0))
        + Coalesce(F('tranche_3_due'), Value(0))
    )
    paye_total = (
        Coalesce(F('frais_inscription_paye'), Value(0))
        + Coalesce(F('tranche_1_payee'), Value(0))
        + Coalesce(F('tranche_2_payee'), Value(0))
        + Coalesce(F('tranche_3_payee'), Value(0))
    )
    remises_total = Coalesce(
        Sum('eleve__paiements__remises__montant_remise', filter=Q(eleve__paiements__statut='VALIDE')),
        Value(0),
        output_field=DecimalField(max_digits=10, decimal_places=0),
    )
    net_sco_du = Greatest(Value(0), ExpressionWrapper(dues_sco - remises_total, output_field=DecimalField(max_digits=10, decimal_places=0)))
    net_du = ExpressionWrapper(
        Coalesce(F('frais_inscription_du'), Value(0)) + net_sco_du,
        output_field=DecimalField(max_digits=10, decimal_places=0),
    )
    solde_calc = ExpressionWrapper(net_du - paye_total, output_field=DecimalField(max_digits=10, decimal_places=0))

    qs = qs.annotate(
        total_du_calc=net_du,
        total_paye_calc=paye_total,
        solde_calcule=solde_calc,
        total_remises_calc=remises_total,
    ).order_by('eleve__classe__nom', 'eleve__nom', 'eleve__prenom')

    # Élèves soldés: solde <= 0
    qs_soldes = qs.filter(solde_calcule__lte=0)

    # Totaux
    aggr = qs_soldes.aggregate(
        du=Coalesce(Sum('total_du_calc'), Value(0)),
        paye=Coalesce(Sum('total_paye_calc'), Value(0)),
        solde=Coalesce(Sum('solde_calcule'), Value(0)),
        remises=Coalesce(Sum('total_remises_calc'), Value(0)),
    )

    # Pagination
    paginator = Paginator(qs_soldes, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    # Options d'écoles/classes
    ecoles_qs = []
    try:
        from eleves.models import Ecole
        ecoles_qs = Ecole.objects.all().order_by('nom')
    except Exception:
        ecoles_qs = []
    classes = Classe.objects.select_related('ecole').all().order_by('ecole__nom', 'nom')

    context = {
        'annee': annee,
        'annees_options': [annee],
        'ecoles': ecoles_qs,
        'classes': classes,
        'ecole_id': ecole_id,
        'classe_id': classe_id,
        'q': q,
        'page_obj': page_obj,
        'totaux': {
            'du': int(aggr['du'] or 0),
            'paye': int(aggr['paye'] or 0),
            'solde': int(aggr['solde'] or 0),
            'remises': int(aggr['remises'] or 0),
        },
        'periode_debut': today.replace(month=9, day=1) if hasattr(today, 'replace') else today,
        'periode_fin': today,
    }
    template = 'paiements/eleves_soldes.html' if _template_exists('paiements/eleves_soldes.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Élèves soldés')

def ajax_statistiques_paiements(request):
    """Retourne les stats du tableau de bord pour mise à jour AJAX."""
    stats = _compute_stats()
    return JsonResponse({
        'success': True,
        'stats': stats,
    })

def ajax_eleve_info(request):
    """Retourne des informations élève + échéancier pour le formulaire paiement.
    Attend un paramètre `matricule` (GET). Utilisé par `templates/paiements/form_paiement.html`.
    """
    matricule = request.GET.get('matricule') or request.POST.get('matricule')
    if not matricule:
        return JsonResponse({'success': False, 'error': 'Matricule requis.'}, status=400)

    try:
        eleve = Eleve.objects.select_related('classe', 'classe__ecole').get(matricule__iexact=matricule)
    except Eleve.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Élève introuvable.'}, status=404)

    # Construire la réponse
    data = {
        'success': True,
        'eleve': {
            'id': eleve.id,
            'matricule': getattr(eleve, 'matricule', ''),
            'nom': getattr(eleve, 'nom', ''),
            'prenom': getattr(eleve, 'prenom', ''),
            'classe': getattr(eleve.classe, 'nom', '') if getattr(eleve, 'classe', None) else '',
            'ecole': getattr(eleve.classe.ecole, 'nom', '') if getattr(eleve, 'classe', None) and getattr(eleve.classe, 'ecole', None) else '',
            'photo_url': (getattr(getattr(eleve, 'photo', None), 'url', None) or ''),
        },
        'echeancier': None,
    }

    # Échéancier (si présent)
    try:
        echeancier = getattr(eleve, 'echeancier', None)
    except Exception:
        echeancier = None

    if echeancier:
        data['echeancier'] = {
            'inscription_du': int(echeancier.frais_inscription_du or 0),
            'inscription_paye': int(echeancier.frais_inscription_paye or 0),
            'tranche_1_du': int(echeancier.tranche_1_due or 0),
            'tranche_1_paye': int(echeancier.tranche_1_payee or 0),
            'tranche_2_du': int(echeancier.tranche_2_due or 0),
            'tranche_2_paye': int(echeancier.tranche_2_payee or 0),
            'tranche_3_du': int(echeancier.tranche_3_due or 0),
            'tranche_3_paye': int(echeancier.tranche_3_payee or 0),
            'total_du': int(echeancier.total_du or 0),
            'total_paye': int(echeancier.total_paye or 0),
        }

    return JsonResponse(data)

def ajax_calculer_remise(request):
    return JsonResponse({'ok': True, 'montant_apres_remise': 0})

def ajax_classes_par_ecole(request):
    return JsonResponse({'ok': True, 'classes': []})

@can_apply_discounts
def appliquer_remise_paiement(request, paiement_id:int):
    """Affiche et traite le formulaire d'application de remises pour un paiement."""
    paiement = get_object_or_404(
        Paiement.objects.select_related('eleve', 'type_paiement', 'mode_paiement'),
        pk=paiement_id,
    )

    # Seuls les paiements en attente peuvent être modifiés
    if getattr(paiement, 'statut', 'EN_ATTENTE') != 'EN_ATTENTE':
        messages.warning(request, "Seuls les paiements en attente peuvent recevoir des remises.")
        return redirect('paiements:detail_paiement', paiement_id=paiement.id)

    # Base scolarité = T1+T2+T3 (hors inscription)
    base_scolarite = 0
    try:
        ech = getattr(paiement.eleve, 'echeancier', None)
        if ech:
            base_scolarite = int((ech.tranche_1_due or 0) + (ech.tranche_2_due or 0) + (ech.tranche_3_due or 0))
        if not base_scolarite:
            # Fallback via grille tarifaire de la classe
            try:
                from eleves.models import GrilleTarifaire as _Grille
                classe = getattr(paiement.eleve, 'classe', None)
                ecole = getattr(classe, 'ecole', None)
                niveau = getattr(classe, 'niveau', None)
                annee = getattr(classe, 'annee_scolaire', None)
                grille = None
                if ecole and niveau and annee:
                    grille = _Grille.objects.filter(ecole=ecole, niveau=niveau, annee_scolaire=annee).first()
                if not grille and ecole and niveau:
                    grille = _Grille.objects.filter(ecole=ecole, niveau=niveau).order_by('-annee_scolaire').first()
                if grille:
                    base_scolarite = int((grille.tranche_1 or 0) + (grille.tranche_2 or 0) + (grille.tranche_3 or 0))
            except Exception:
                pass
    except Exception:
        base_scolarite = 0

    if request.method == 'POST':
        form = PaiementRemiseForm(request.POST, paiement=paiement)
        if form.is_valid():
            remises = form.cleaned_data.get('remises') or []
            pct_str = form.cleaned_data.get('pourcentage_scolarite') or ''
            try:
                pct_value = int(pct_str) if str(pct_str).isdigit() else 0
            except Exception:
                pct_value = 0
            # Si aucune remise n'est sélectionnée, ne rien modifier et afficher une erreur
            if not remises and pct_value <= 0:
                messages.error(request, "Aucune remise sélectionnée. Aucune modification n'a été effectuée.")
                try:
                    remises_existantes = list(paiement.remises.select_related('remise').all())
                except Exception:
                    remises_existantes = []
                context = {
                    'paiement': paiement,
                    'form': form,
                    'remises_existantes': remises_existantes,
                    'base_scolarite': int(base_scolarite or 0),
                }
                return render(request, 'paiements/appliquer_remise.html', context)

            # pourcentage_scolarite est un aperçu UI, on ne le persiste pas ici faute de modèle dédié
            with transaction.atomic():
                # Remplacer les remises existantes par la sélection
                PaiementRemise.objects.filter(paiement=paiement).delete()
                created = 0
                for remise in remises:
                    try:
                        montant_remise = remise.calculer_remise(paiement.montant)
                    except Exception:
                        montant_remise = 0
                    PaiementRemise.objects.create(
                        paiement=paiement,
                        remise=remise,
                        montant_remise=montant_remise,
                    )
                    created += 1

                # Appliquer également la remise scolarité (%) si choisie
                if pct_value > 0:
                    from datetime import date
                    annee = paiement.date_paiement.year
                    # Chercher une remise existante "Remise scolarité X%" active et couvrant la date
                    nom_remise = f"Remise scolarité {pct_value}%"
                    remise_pct = RemiseReduction.objects.filter(
                        nom=nom_remise,
                        type_remise='POURCENTAGE',
                        valeur=pct_value,
                        actif=True,
                        date_debut__lte=paiement.date_paiement,
                        date_fin__gte=paiement.date_paiement,
                    ).first()
                    if not remise_pct:
                        # Créer une remise "technique" pour l'année en cours
                        remise_pct = RemiseReduction.objects.create(
                            nom=nom_remise,
                            type_remise='POURCENTAGE',
                            valeur=pct_value,
                            motif='AUTRE',
                            description="Remise scolarité variable (technique)",
                            date_debut=date(annee, 1, 1),
                            date_fin=date(annee, 12, 31),
                            actif=True,
                        )
                    # 3% s'applique sur base scolarité (T1+T2+T3), pas sur le montant du paiement
                    try:
                        montant_remise_pct = (base_scolarite * pct_value) / 100
                    except Exception:
                        montant_remise_pct = (paiement.montant * pct_value) / 100
                    # Ne jamais dépasser le montant du paiement
                    try:
                        from decimal import Decimal as _D
                        montant_remise_pct = min(_D(montant_remise_pct), _D(paiement.montant))
                    except Exception:
                        try:
                            montant_remise_pct = min(float(montant_remise_pct), float(paiement.montant))
                        except Exception:
                            pass
                    PaiementRemise.objects.create(
                        paiement=paiement,
                        remise=remise_pct,
                        montant_remise=montant_remise_pct,
                    )
                    created += 1
            messages.success(request, f"Remises appliquées: {created}.")
            return redirect('paiements:detail_paiement', paiement_id=paiement.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire de remises.")
    else:
        form = PaiementRemiseForm(paiement=paiement)

    # Remises déjà liées au paiement (pour affichage et cases cochées)
    try:
        remises_existantes = list(paiement.remises.select_related('remise').all())
    except Exception:
        remises_existantes = []

    context = {
        'paiement': paiement,
        'form': form,
        'remises_existantes': remises_existantes,
        'base_scolarite': int(base_scolarite or 0),
    }
    return render(request, 'paiements/appliquer_remise.html', context)

def calculateur_remise(request):
    return HttpResponse('Calculateur de remise (placeholder)')

def _template_exists(path:str)->bool:
    """Utilitaire léger: détecte si un template existe dans le chargeur Django."""
    try:
        from django.template.loader import get_template
        get_template(path)
        return True
    except Exception:
        return False
