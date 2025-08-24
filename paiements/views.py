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
# Placeholders temporaires pour les vues attendues par paiements/urls.py
# À remplacer par les implémentations réelles si nécessaire.
# ---------------------------------------------------------------

def tableau_bord_paiements(request):
    return render(request, 'paiements/tableau_bord.html', context={}) if _template_exists('paiements/tableau_bord.html') else HttpResponse('Tableau de bord paiements (placeholder)')

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

    # Compteurs par statut sur l'ensemble des résultats (sans filtrer par statut sélectionné)
    qs_for_counts = qs
    stats = {
        'total': qs_for_counts.exclude(statut='ANNULE').count() if hasattr(Paiement, 'STATUT_CHOICES') else qs_for_counts.count(),
        'valide': qs_for_counts.filter(statut='VALIDE').count(),
        'attente': qs_for_counts.filter(statut='EN_ATTENTE').count(),
    }

    # Filtre par statut (si fourni)
    if statut:
        qs = qs.filter(statut=statut)

    # Pagination
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)

    context = {
        'titre_page': titre_page,
        'q': q,
        'statut': statut,
        'paiements': page_obj.object_list,
        'page_obj': page_obj,
        'stats': stats,
    }

    template = 'paiements/liste_paiements.html' if _template_exists('paiements/liste_paiements.html') else None
    if template:
        return render(request, template, context)
    return HttpResponse('Liste des paiements')

def detail_paiement(request, paiement_id:int):
    return HttpResponse(f'Détail paiement {paiement_id} (placeholder)')

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
            messages.success(request, "Paiement enregistré avec succès. En attente de validation.")
            try:
                return redirect('paiements:detail_paiement', paiement_id=paiement.id)
            except Exception:
                # Si la vue de détail n'est pas prête, retour à l'échéancier de l'élève
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
    return HttpResponse(f'Valider paiement {paiement_id} (placeholder)')

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
    return HttpResponse(f'Échéancier élève {eleve_id} (placeholder)')

def creer_echeancier(request, eleve_id:int):
    return HttpResponse(f'Créer échéancier élève {eleve_id} (placeholder)')

def generer_recu_pdf(request, paiement_id:int):
    return HttpResponse(f'Reçu PDF paiement {paiement_id} (placeholder)', content_type='application/pdf')

def export_liste_paiements_excel(request):
    response = HttpResponse('excel,placeholder', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="paiements.xlsx"'
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
    return JsonResponse({
        'total_paiements': 0,
        'total_valide': 0,
        'eleves_en_retard': 0,
        'paiements_en_attente': 0,
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
    return HttpResponse(f'Appliquer remise paiement {paiement_id} (placeholder)')

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
