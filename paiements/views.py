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
from django.db.models import F, ExpressionWrapper, DecimalField
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side, numbers

from .models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise, Relance, TwilioInboundMessage
from eleves.models import Eleve, GrilleTarifaire, Classe
from .forms import PaiementForm, EcheancierForm, RechercheForm
from .remise_forms import PaiementRemiseForm, CalculateurRemiseForm
from utilisateurs.utils import user_is_admin, filter_by_user_school, user_school
from utilisateurs.permissions import can_add_payments, can_modify_payments, can_delete_payments, can_validate_payments, can_view_reports
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

    # Élèves en retard: solde restant > 0
    solde_expr = (
        F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due')
        - (F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'))
    )
    eleves_retard_count = (
        EcheancierPaiement.objects
        .annotate(solde=ExpressionWrapper(solde_expr, output_field=DecimalField(max_digits=10, decimal_places=0)))
        .filter(solde__gt=0)
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

    # Top élèves en retard (solde décroissant) – NOTE: ne pas annoter "solde_restant" (collision avec @property)
    solde_expr = (
        F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due')
        - (F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'))
    )
    eleves_en_retard = (
        EcheancierPaiement.objects
        .select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
        .annotate(solde_db=ExpressionWrapper(solde_expr, output_field=DecimalField(max_digits=10, decimal_places=0)))
        .filter(solde_db__gt=0)
        .order_by('-solde_db')[:10]
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

    context = {
        'titre_page': f"Détail du paiement #{paiement.id}",
        'paiement': paiement,
        'is_admin': user_is_admin(request.user) if request.user.is_authenticated else False,
        'user_permissions': perms_ctx,
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

    # Annoter solde restant au niveau DB pour filtrer efficacement
    solde_expr = (
        F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due')
        - (F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'))
    )
    qs = (
        EcheancierPaiement.objects.select_related('eleve', 'eleve__classe')
        .annotate(solde=ExpressionWrapper(solde_expr, output_field=DecimalField(max_digits=10, decimal_places=0)))
        .filter(solde__gt=0)
    )
    envoyes = 0
    for ech in qs[:500]:  # sécurité: batch max 500
        try:
            send_retard_notification(ech.eleve, ech.solde)
            envoyes += 1
        except Exception:
            logging.getLogger(__name__).exception("Échec envoi retard pour %s", getattr(ech.eleve, 'nom_complet', 'eleve'))
            continue
    messages.info(request, f"Notifications de retard envoyées: {envoyes} (sur {qs.count()} éligibles)")
    # Rediriger vers relances ou tableau de bord
    return redirect('paiements:liste_relances')

def liste_relances(request):
    """Liste des relances (UI existante, données placeholder)."""
    titre_page = "Liste des relances"
    q = request.GET.get('q', '').strip()
    canal = request.GET.get('canal', '')
    statut = request.GET.get('statut', '')
    context = {
        'titre_page': titre_page,
        'q': q,
        'canal': canal,
        'statut': statut,
        'page_obj': [],
    }
    template = 'paiements/relances.html' if _template_exists('paiements/relances.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Liste des relances (placeholder)')

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
    }
    return render(request, 'paiements/form_echeancier.html', context)

def generer_recu_pdf(request, paiement_id:int):
    return HttpResponse(f'Reçu PDF paiement {paiement_id} (placeholder)', content_type='application/pdf')

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
    """Rapport de remises – rend le template avec totaux/rows vides."""
    titre_page = "Rapport des remises"
    q = request.GET.get('q', '').strip()
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    context = {
        'titre_page': titre_page,
        'q': q,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'rows': [],
        'total_global': 0,
    }
    template = 'paiements/rapport_remises.html' if _template_exists('paiements/rapport_remises.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Rapport remises (placeholder)')

def liste_eleves_soldes(request):
    """Élèves soldés – rend la page avec filtres et totaux en placeholder."""
    from django.utils import timezone as _tz
    today = _tz.localdate() if hasattr(_tz, 'localdate') else date.today()
    annee = request.GET.get('annee') or f"{today.year}-{today.year+1}"
    ecole_id = request.GET.get('ecole_id', '')
    classe_id = request.GET.get('classe_id', '')
    q = request.GET.get('q', '').strip()

    context = {
        'annee': annee,
        'annees_options': [annee],
        'ecoles': [],
        'classes': [],
        'ecole_id': ecole_id,
        'classe_id': classe_id,
        'q': q,
        'page_obj': [],
        'totaux': {
            'du': 0,
            'paye': 0,
            'solde': 0,
            'remises': 0,
        },
        'periode_debut': today.replace(month=9, day=1) if hasattr(today, 'replace') else today,
        'periode_fin': today,
    }
    template = 'paiements/eleves_soldes.html' if _template_exists('paiements/eleves_soldes.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Élèves soldés (placeholder)')

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

    if request.method == 'POST':
        form = PaiementRemiseForm(request.POST, paiement=paiement)
        if form.is_valid():
            remises = form.cleaned_data.get('remises') or []
            # pourcentage_scolarite est un aperçu UI, on ne le persiste pas ici faute de modèle dédié
            with transaction.atomic():
                # Supprimer les remises existantes puis recréer selon la sélection
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
