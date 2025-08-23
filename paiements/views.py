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
from django.core.paginator import Paginator
from decimal import Decimal
from datetime import date, datetime
import os

from .models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise, Relance
from eleves.models import Eleve, GrilleTarifaire, Classe
from .forms import PaiementForm, EcheancierForm, RechercheForm
from .remise_forms import PaiementRemiseForm, CalculateurRemiseForm
from utilisateurs.utils import user_is_admin, filter_by_user_school, user_school
from utilisateurs.permissions import can_add_payments, can_modify_payments, can_delete_payments, can_validate_payments, can_view_reports
# Removed incorrect imports from rapports.utils (format_currency, ensure_current_academic_year not present)
from django.views.decorators.http import require_http_methods
import re
import unicodedata

# Filigrane PDF partagé
from ecole_moderne.pdf_utils import draw_logo_watermark

# --- Configuration des tolérances (ajustables) ---
# Tolérance absolue pour la détection "Inscription + 1ère tranche"
TOLERANCE_INSCRIPTION_T1 = Decimal('50000')  # 50 000 GNF
# Tolérance relative (pourcentage) pour la détection de paiement annuel
TOLERANCE_ANNUEL_PERCENT = Decimal('0.10')   # ±10%

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

def _tuition_annual_by_cycle(eleve: Eleve) -> Decimal:
    """Retourne le montant annuel de scolarité selon l'école et le cycle/classe de l'élève.
    Sources fournies (Sonfonia: montants annuels + 3%, Somayah: totaux par tranches):
    - Sonfonia:
      Garderie=2_800_000; Maternelle=2_000_000; Primaire 1-4=1_700_000; Primaire 5-6=2_000_000;
      Collège 7-8=2_100_000; Collège 9-10=2_300_000; Lycée 11=2_200_000; Lycée 12=2_400_000; Terminales=2_800_000
    - Somayah:
      Maternelle=1_500_000; Primaire (1-5)=1_350_000; Primaire (6)=1_800_000; Collège (7-9)=1_620_000;
      Collège (10)=1_800_000; Lycée (11-12)=1_710_000
    """
    try:
        from decimal import Decimal as _D
        ecole_nom = (getattr(getattr(eleve.classe, 'ecole', None), 'nom', '') or '').strip().lower()
        classe_nom = (getattr(eleve.classe, 'nom', '') or '').strip().lower()

        def has_any(s, arr):
            s = s or ''
            return any(x in s for x in arr)

        is_somayah = 'somayah' in ecole_nom

        # Normalisations simples
        is_garderie = has_any(classe_nom, ['garderie'])
        is_maternelle = has_any(classe_nom, ['maternelle']) and not is_garderie
        is_primaire = has_any(classe_nom, ['primaire', 'pn', 'cn', 'classe primaire'])
        is_college = has_any(classe_nom, ['collège', 'college', 'cn7', 'cn8', 'cn9', 'cn10', '7', '8', '9', '10']) and not is_primaire and not is_maternelle
        is_lycee = has_any(classe_nom, ['lycée', 'lycee', 'l11', 'l12', 'terminal']) and not is_college

        # Détecter niveau numérique s'il est présent dans le nom
        niveau_num = None
        import re as _re
        m = _re.search(r"(\b|\D)([0-9]{1,2})(\b|\D)", classe_nom)
        if m:
            try:
                niveau_num = int(m.group(2))
            except Exception:
                niveau_num = None

        if is_somayah:
            # Barèmes Somayah
            if is_maternelle:
                return _D('1500000')
            if is_primaire:
                if niveau_num == 6:
                    return _D('1800000')
                return _D('1350000')  # 1-5
            if is_college:
                if niveau_num == 10:
                    return _D('1800000')
                return _D('1620000')  # 7-9
            if is_lycee:
                return _D('1710000')  # 11-12
            # Fallback générique Somayah
            return _D('1500000') if is_maternelle else _D('1350000')
        else:
            # Barèmes Sonfonia (Groupe Hadja Kanfing Diané)
            if is_garderie:
                return _D('2800000')
            if is_maternelle:
                return _D('2000000')
            if is_primaire:
                if niveau_num in (5, 6):
                    return _D('2000000')  # 5e-6e
                return _D('1700000')  # 1-4
            if is_college:
                if niveau_num in (9, 10):
                    return _D('2300000')
                return _D('2100000')  # 7-8
            if is_lycee:
                if niveau_num == 11:
                    return _D('2200000')
                if niveau_num == 12:
                    return _D('2400000')
                # Terminales (autres)
                return _D('2800000')
            # Fallback Sonfonia
            return _D('2000000')
    except Exception:
        return Decimal('0')

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
    """Distribue le montant sur les lignes de l'échéancier selon les règles métier améliorées.
    
    Règles:
    1. Si paiement = Inscription + 1ère tranche : déduire automatiquement 30,000 GNF pour inscription
    2. Si paiement annuel : répartir sur toutes les tranches
    3. Validation des surpaiements par tranche
    
    Renvoie un dict: {warnings: [..], info: [..]}
    """
    warnings = []
    infos = []

    # Snapshot avant paiement
    total_paye_avant = echeancier.total_paye
    solde_avant = echeancier.solde_restant
    
    # Constantes
    FRAIS_INSCRIPTION = Decimal('30000')
    
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

    # Calculer les soldes restants par tranche
    inscription_restant = max(Decimal('0'), echeancier.frais_inscription_du - echeancier.frais_inscription_paye)
    t1_restant = max(Decimal('0'), echeancier.tranche_1_due - echeancier.tranche_1_payee)
    t2_restant = max(Decimal('0'), echeancier.tranche_2_due - echeancier.tranche_2_payee)
    t3_restant = max(Decimal('0'), echeancier.tranche_3_due - echeancier.tranche_3_payee)
    
    scolarite_restante = t1_restant + t2_restant + t3_restant
    total_restant = inscription_restant + scolarite_restante
    
    # Garder en mémoire les montants des tranches pour validation
    tranches_info = {
        'inscription': {
            'du': echeancier.frais_inscription_du,
            'paye': echeancier.frais_inscription_paye,
            'restant': inscription_restant,
            'label': 'Frais d\'inscription'
        },
        't1': {
            'du': echeancier.tranche_1_due,
            'paye': echeancier.tranche_1_payee,
            'restant': t1_restant,
            'label': '1ère tranche'
        },
        't2': {
            'du': echeancier.tranche_2_due,
            'paye': echeancier.tranche_2_payee,
            'restant': t2_restant,
            'label': '2ème tranche'
        },
        't3': {
            'du': echeancier.tranche_3_due,
            'paye': echeancier.tranche_3_payee,
            'restant': t3_restant,
            'label': '3ème tranche'
        }
    }
    
    # Fonction de validation des surpaiements
    def valider_surpaiement(tranche_key, montant_a_payer):
        """Valide qu'un montant ne dépasse pas le solde restant d'une tranche"""
        info = tranches_info[tranche_key]
        if montant_a_payer > info['restant']:
            return f"ERREUR: Le montant ({montant_a_payer:,.0f} GNF) dépasse le solde restant de {info['label']} ({info['restant']:,.0f} GNF)"
        return None
    
    restant = Decimal(montant)
    
    # **RÈGLE 1: Détection automatique Inscription + 1ère tranche**
    if (inscription_restant > 0 and t1_restant > 0 and 
        restant >= (FRAIS_INSCRIPTION + t1_restant) and 
        restant <= (FRAIS_INSCRIPTION + t1_restant + TOLERANCE_INSCRIPTION_T1)):
        
        # Validation des surpaiements AVANT traitement
        montant_inscription_prevu = min(FRAIS_INSCRIPTION, inscription_restant)
        montant_t1_prevu = min(restant - montant_inscription_prevu, t1_restant)
        
        erreur_inscription = valider_surpaiement('inscription', montant_inscription_prevu)
        erreur_t1 = valider_surpaiement('t1', montant_t1_prevu)
        
        if erreur_inscription:
            warnings.append(erreur_inscription)
            return {'warnings': warnings, 'info': infos}
        if erreur_t1:
            warnings.append(erreur_t1)
            return {'warnings': warnings, 'info': infos}
        
        infos.append(f"Détection automatique: Frais d'inscription ({montant_inscription_prevu:,.0f} GNF) + 1ère tranche ({montant_t1_prevu:,.0f} GNF)")
        
        # Payer l'inscription
        echeancier.frais_inscription_paye += montant_inscription_prevu
        restant -= montant_inscription_prevu
        
        # Payer la 1ère tranche avec le reste
        echeancier.tranche_1_payee += montant_t1_prevu
        restant -= montant_t1_prevu
        
        if restant > 0:
            warnings.append(f"Excédent de {restant:,.0f} GNF après paiement inscription + 1ère tranche")
    
    # **RÈGLE 2: Paiement annuel (scolarité complète)**
    elif (
        inscription_restant == 0 and
        restant >= scolarite_restante * (Decimal('1') - TOLERANCE_ANNUEL_PERCENT) and 
        restant <= scolarite_restante * (Decimal('1') + TOLERANCE_ANNUEL_PERCENT)
    ):
        
        # Répartir proportionnellement sur les tranches restantes
        tranches_actives = []
        if t1_restant > 0:
            tranches_actives.append(('t1', t1_restant))
        if t2_restant > 0:
            tranches_actives.append(('t2', t2_restant))
        if t3_restant > 0:
            tranches_actives.append(('t3', t3_restant))
        
        if tranches_actives:
            # Calculer les montants prévus et valider AVANT traitement
            montants_prevus = {}
            restant_temp = restant
            
            for i, (tranche_key, tranche_restant) in enumerate(tranches_actives):
                if i == len(tranches_actives) - 1:  # Dernière tranche = tout le reste
                    montant_tranche = restant_temp
                else:
                    proportion = tranche_restant / scolarite_restante
                    montant_tranche = restant * proportion
                
                # Validation: pas de surpaiement
                montant_tranche = min(montant_tranche, tranche_restant)
                montants_prevus[tranche_key] = montant_tranche
                restant_temp -= montant_tranche
                
                # Validation avec fonction centralisée
                erreur = valider_surpaiement(tranche_key, montant_tranche)
                if erreur:
                    warnings.append(erreur)
                    return {'warnings': warnings, 'info': infos}
            
            infos.append(f"Détection: Paiement annuel de scolarité ({restant:,.0f} GNF)")
            
            # Appliquer les paiements après validation
            for tranche_key, montant_tranche in montants_prevus.items():
                if tranche_key == 't1':
                    echeancier.tranche_1_payee += montant_tranche
                elif tranche_key == 't2':
                    echeancier.tranche_2_payee += montant_tranche
                elif tranche_key == 't3':
                    echeancier.tranche_3_payee += montant_tranche
                
                restant -= montant_tranche
                
                if restant <= 0:
                    break
    
    # **RÈGLE 3: Paiement ciblé ou séquentiel normal**
    else:
        # Définition des tranches dans l'ordre à payer
        ordre = ['inscription', 't1', 't2', 't3']
        if cible in ordre:
            # Paiement ciblé: appliquer séquentiellement depuis le début jusqu'à la tranche ciblée
            # Exemple: cible = t2 => compléter inscription puis T1 avant T2
            for key in ordre:
                if restant <= 0:
                    break
                # Arrêter après avoir traité la tranche ciblée
                # (on ne dépasse pas la tranche ciblée lors d'un paiement ciblé)
                due_field, paid_field, due_date_field, label = tranche_data(key)
                due = getattr(echeancier, due_field)
                paid = getattr(echeancier, paid_field)
                to_pay = max(Decimal('0'), due - paid)
                if to_pay <= 0:
                    # Déjà soldée, passer à la suivante
                    # Continuer même si key == cible pour permettre d'aller jusqu'à la cible
                    pass
                else:
                    pay_now = min(restant, to_pay)
                    # Validation surpaiement pour la tranche courante
                    erreur = valider_surpaiement(key, pay_now)
                    if erreur:
                        warnings.append(erreur)
                        return {'warnings': warnings, 'info': infos}

                    # Vérifier le retard pour la tranche courante
                    due_date = getattr(echeancier, due_date_field)
                    if date_pay > due_date:
                        delta = (date_pay - due_date).days
                        warnings.append(f"Retard sur {label}: {delta} jour(s) après l'échéance ({due_date.strftime('%d/%m/%Y')})")

                    # Appliquer le paiement pour la tranche courante
                    setattr(echeancier, paid_field, paid + pay_now)
                    restant -= pay_now

                # Si on a atteint la tranche ciblée, on ne s'arrête que si tout le montant a été alloué
                # Cela évite d'avoir un "montant non alloué" alors qu'il reste d'autres tranches à couvrir
                if key == cible and restant <= 0:
                    break
        else:
            # Paiement séquentiel normal avec validation à chaque étape
            for key in ordre:
                if restant <= 0:
                    break
                due_field, paid_field, due_date_field, label = tranche_data(key)
                due = getattr(echeancier, due_field)
                paid = getattr(echeancier, paid_field)
                to_pay = max(Decimal('0'), due - paid)
                if to_pay <= 0:
                    continue

                # Calculer le montant à payer pour cette tranche
                pay_now = min(restant, to_pay)
                
                # Validation avec fonction centralisée
                erreur = valider_surpaiement(key, pay_now)
                if erreur:
                    warnings.append(erreur)
                    return {'warnings': warnings, 'info': infos}

                # Vérification de retard
                due_date = getattr(echeancier, due_date_field)
                if date_pay > due_date:
                    delta = (date_pay - due_date).days
                    warnings.append(f"Retard sur {label}: {delta} jour(s) après l'échéance ({due_date.strftime('%d/%m/%Y')})")

                # Appliquer le paiement après validation
                setattr(echeancier, paid_field, paid + pay_now)
                restant -= pay_now

    # Vérification finale des surpaiements
    if restant > 0:
        warnings.append(f"ATTENTION: Excédent de {restant:,.0f} GNF non alloué")

    # Mettre à jour le statut
    nouveau_solde = echeancier.solde_restant
    if nouveau_solde <= 0:
        echeancier.statut = 'PAYE_COMPLET'
        if nouveau_solde < 0:
            warnings.append(f"Surpaiement détecté: {abs(nouveau_solde):,.0f} GNF")
    else:
        # Vérifier s'il existe du retard résiduel
        now = date_pay
        en_retard = (
            (now > echeancier.date_echeance_inscription and echeancier.frais_inscription_paye < echeancier.frais_inscription_du) or
            (now > echeancier.date_echeance_tranche_1 and echeancier.tranche_1_payee < echeancier.tranche_1_due) or
            (now > echeancier.date_echeance_tranche_2 and echeancier.tranche_2_payee < echeancier.tranche_2_due) or
            (now > echeancier.date_echeance_tranche_3 and echeancier.tranche_3_payee < echeancier.tranche_3_due)
        )
        echeancier.statut = 'EN_RETARD' if en_retard else 'PAYE_PARTIEL'

    # Message de félicitation pour paiement complet
    if total_paye_avant == 0 and nouveau_solde <= 0:
        infos.append("🎉 Toutes les tranches ont été réglées ! Merci pour votre paiement.")

    # Persister les modifications de l'échéancier
    # Important: cette fonction peut être appelée via délégation depuis _allocate_combined_payment,
    # il faut donc sauvegarder ici pour éviter de perdre les mises à jour.
    echeancier.save()

    return {'warnings': warnings, 'info': infos}


@login_required
def liste_eleves_soldes(request):
    """Liste des élèves ayant soldé l'année scolaire (solde <= 0), en tenant compte des remises.

    Filtres GET pris en charge:
    - annee: ex "2024-2025" (par défaut: année courante inférée)
    - ecole_id: id de l'école
    - classe_id: id de la classe
    - q: recherche (nom/matricule)
    """
    # Permissions: admins ou comptables (validation)
    if not (user_is_admin(request.user) or can_validate_payments(request.user)):
        messages.error(request, "Accès refusé: droits insuffisants.")
        return redirect('paiements:tableau_bord')

    from django.db.models import F

    annee = (request.GET.get('annee') or '').strip()
    q = (request.GET.get('q') or '').strip()
    ecole_id = request.GET.get('ecole_id')
    classe_id = request.GET.get('classe_id')

    # Déterminer l'année scolaire par défaut si vide
    if not annee:
        # Demande: par défaut utiliser 2025-2026
        annee = "2025-2026"

    # Fenêtre temporelle pour l'année scolaire (1er Sep -> 31 Août)
    def _borne_dates_annee(annee_scolaire: str):
        try:
            deb, fin = _annee_vers_dates(annee_scolaire)
            from datetime import date as _d
            date_debut = _d(deb, 9, 1)
            date_fin = _d(fin, 8, 31)
            return date_debut, date_fin
        except Exception:
            from datetime import date as _d
            y = date.today().year
            if date.today().month >= 9:
                return _d(y, 9, 1), _d(y+1, 8, 31)
            return _d(y-1, 9, 1), _d(y, 8, 31)

    periode_debut, periode_fin = _borne_dates_annee(annee)

    # Base queryset: échéanciers de l'année
    echeanciers = EcheancierPaiement.objects.filter(annee_scolaire=annee)

    # Filtre par école pour non-admins
    if not user_is_admin(request.user):
        echeanciers = filter_by_user_school(echeanciers, request.user, 'eleve__classe__ecole')

    # Filtres facultatifs
    if ecole_id:
        echeanciers = echeanciers.filter(eleve__classe__ecole_id=ecole_id)
    if classe_id:
        echeanciers = echeanciers.filter(eleve__classe_id=classe_id)
    if q:
        echeanciers = echeanciers.filter(
            Q(eleve__prenom__icontains=q) | Q(eleve__nom__icontains=q) | Q(eleve__matricule__icontains=q)
        )

    # Annoter solde et filtrer soldés (éviter collision avec @property total_du/total_paye)
    echeanciers = echeanciers.annotate(
        total_du_calc=F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due'),
        total_paye_calc=F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'),
        solde_calcule=F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due') - (
            F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
        )
    ).filter(Q(solde_calcule__lte=0) | Q(statut='PAYE_COMPLET'))

    # Tri: par classe puis prénom/nom
    echeanciers = echeanciers.select_related('eleve__classe__ecole').order_by('eleve__classe__nom', 'eleve__prenom', 'eleve__nom')

    # Totaux généraux pour l'ensemble du résultat filtré (non paginé)
    qs_all = echeanciers
    from django.db.models import Sum
    agg = qs_all.aggregate(
        total_du_sum=Sum(
            F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due')
        ),
        total_paye_sum=Sum(
            F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
        ),
        solde_sum=Sum(
            F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due') - (
                F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
            )
        )
    )
    total_du_sum = agg.get('total_du_sum') or 0
    total_paye_sum = agg.get('total_paye_sum') or 0
    solde_sum = agg.get('solde_sum') or 0

    # Total remises globales sur la période pour ces élèves
    eleves_ids_all = list(qs_all.values_list('eleve_id', flat=True))
    total_remises_sum = 0
    if eleves_ids_all:
        pay_ids_all = list(Paiement.objects.filter(
            eleve_id__in=eleves_ids_all,
            date_paiement__range=(periode_debut, periode_fin)
        ).exclude(statut='ANNULE').values_list('id', flat=True))
        if pay_ids_all:
            total_remises_sum = PaiementRemise.objects.filter(paiement_id__in=pay_ids_all).aggregate(s=Sum('montant_remise'))['s'] or 0

    # Pagination
    paginator = Paginator(echeanciers, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calcul des remises par élève sur la période
    remises_map = {}
    paiements_ids_map = {}
    for ech in page_obj:
        # Paiements de l'élève sur l'année (statut != ANNULE)
        paiements_eleves = Paiement.objects.filter(
            eleve=ech.eleve,
            date_paiement__range=(periode_debut, periode_fin)
        ).exclude(statut='ANNULE')
        paiements_ids = list(paiements_eleves.values_list('id', flat=True))
        paiements_ids_map[ech.id] = paiements_ids
        if paiements_ids:
            total_remises = PaiementRemise.objects.filter(paiement_id__in=paiements_ids).aggregate(s=Sum('montant_remise'))['s'] or 0
        else:
            total_remises = 0
        remises_map[ech.id] = total_remises
        # Attacher la valeur directement à l'objet pour simplifier le template
        try:
            setattr(ech, 'total_remises_calc', total_remises)
        except Exception:
            pass

    # Options d'années scolaires pour le select (ex: 2023-2024 à 2028-2029)
    try:
        deb, fin = _annee_vers_dates(annee)
    except Exception:
        deb = date.today().year
        fin = deb + 1
    annees_options = []
    for start in range(deb - 2, deb + 3):
        annees_options.append(f"{start}-{start+1}")

    # Listes déroulantes: écoles et classes
    from eleves.models import Ecole, Classe as MClasse
    if user_is_admin(request.user):
        ecoles_qs = Ecole.objects.all().order_by('nom')
    else:
        us = user_school(request.user)
        ecoles_qs = Ecole.objects.filter(id=getattr(us, 'id', None)).order_by('nom') if us else Ecole.objects.none()

    classes_qs = MClasse.objects.filter(annee_scolaire=annee)
    if ecole_id:
        classes_qs = classes_qs.filter(ecole_id=ecole_id)
    classes_qs = classes_qs.order_by('ecole__nom', 'nom')

    context = {
        'annee': annee,
        'periode_debut': periode_debut,
        'periode_fin': periode_fin,
        'page_obj': page_obj,
        'remises_map': remises_map,
        'totaux': {
            'du': total_du_sum,
            'paye': total_paye_sum,
            'solde': solde_sum,
            'remises': total_remises_sum,
        },
        'ecole_id': ecole_id,
        'classe_id': classe_id,
        'q': q,
        'annees_options': annees_options,
        'ecoles': ecoles_qs,
        'classes': classes_qs,
    }

    return render(request, 'paiements/eleves_soldes.html', context)

def _allocate_combined_payment(paiement, echeancier):
    """
    Allocation intelligente des paiements combinés selon le type de paiement.
    Répartit automatiquement le montant dans les bonnes colonnes de l'échéancier.
    """
    # Normaliser le libellé pour des correspondances robustes
    raw_nom = (paiement.type_paiement.nom or '').strip()
    type_paiement_nom = unicodedata.normalize('NFKD', raw_nom).encode('ascii', 'ignore').decode('ascii').lower()
    type_paiement_nom = re.sub(r"\s+", " ", type_paiement_nom)
    montant_total = paiement.montant
    warnings = []
    infos = []
    
    # Montants fixes
    FRAIS_INSCRIPTION = Decimal('30000')
    
    # Calculer les montants dus pour chaque tranche
    inscription_due = echeancier.frais_inscription_du or Decimal('0')
    tranche_1_due = echeancier.tranche_1_due or Decimal('0')
    tranche_2_due = echeancier.tranche_2_due or Decimal('0')
    tranche_3_due = echeancier.tranche_3_due or Decimal('0')
    
    # Calculer les montants déjà payés
    inscription_payee = echeancier.frais_inscription_paye or Decimal('0')
    tranche_1_payee = echeancier.tranche_1_payee or Decimal('0')
    tranche_2_payee = echeancier.tranche_2_payee or Decimal('0')
    tranche_3_payee = echeancier.tranche_3_payee or Decimal('0')
    
    # Calculer les soldes restants
    inscription_restante = max(Decimal('0'), inscription_due - inscription_payee)
    tranche_1_restante = max(Decimal('0'), tranche_1_due - tranche_1_payee)
    tranche_2_restante = max(Decimal('0'), tranche_2_due - tranche_2_payee)
    tranche_3_restante = max(Decimal('0'), tranche_3_due - tranche_3_payee)
    
    # Variables pour la répartition
    montant_restant = montant_total
    allocations = {
        'inscription': Decimal('0'),
        'tranche_1': Decimal('0'),
        'tranche_2': Decimal('0'),
        'tranche_3': Decimal('0')
    }
    
    # Indicateurs flexibles (robustes aux variations d'accents et d'espaces)
    has_insc = 'inscription' in type_paiement_nom or 'insc' in type_paiement_nom
    has_annuel = 'annuel' in type_paiement_nom or 'annuelle' in type_paiement_nom
    has_t1 = 'tranche 1' in type_paiement_nom or '1ere tranche' in type_paiement_nom or '1er tranche' in type_paiement_nom or 't1' in type_paiement_nom
    has_t2 = 'tranche 2' in type_paiement_nom or '2eme tranche' in type_paiement_nom or 't2' in type_paiement_nom
    has_t3 = 'tranche 3' in type_paiement_nom or '3eme tranche' in type_paiement_nom or 't3' in type_paiement_nom
    has_any_tranche = ('tranche' in type_paiement_nom) or has_t1 or has_t2 or has_t3

    # Logique de répartition selon le type de paiement
    if has_insc and has_t1 and not has_t2 and not has_t3 and not has_annuel:
        # Frais d'inscription + 1ère tranche
        infos.append("🔄 Paiement combiné détecté: Inscription + 1ère tranche")
        
        # Allouer l'inscription
        if inscription_restante > 0:
            montant_inscription = min(FRAIS_INSCRIPTION, inscription_restante, montant_restant)
            allocations['inscription'] = montant_inscription
            montant_restant -= montant_inscription
            infos.append(f"✓ Inscription: {int(montant_inscription):,} GNF".replace(',', ' '))
        
        # Allouer le reste à la 1ère tranche
        if montant_restant > 0 and tranche_1_restante > 0:
            montant_tranche_1 = min(tranche_1_restante, montant_restant)
            allocations['tranche_1'] = montant_tranche_1
            montant_restant -= montant_tranche_1
            infos.append(f"✓ 1ère tranche: {int(montant_tranche_1):,} GNF".replace(',', ' '))
    
    elif has_insc and has_t1 and has_t2 and not has_t3 and not has_annuel:
        # Frais d'inscription + 1ère tranche + 2ème tranche
        infos.append("🔄 Paiement combiné détecté: Inscription + 1ère + 2ème tranche")
        
        # Allouer l'inscription
        if inscription_restante > 0:
            montant_inscription = min(FRAIS_INSCRIPTION, inscription_restante, montant_restant)
            allocations['inscription'] = montant_inscription
            montant_restant -= montant_inscription
            infos.append(f"✓ Inscription: {int(montant_inscription):,} GNF".replace(',', ' '))
        
        # Allouer à la 1ère tranche
        if montant_restant > 0 and tranche_1_restante > 0:
            montant_tranche_1 = min(tranche_1_restante, montant_restant)
            allocations['tranche_1'] = montant_tranche_1
            montant_restant -= montant_tranche_1
            infos.append(f"✓ 1ère tranche: {int(montant_tranche_1):,} GNF".replace(',', ' '))
        
        # Allouer le reste à la 2ème tranche
        if montant_restant > 0 and tranche_2_restante > 0:
            montant_tranche_2 = min(tranche_2_restante, montant_restant)
            allocations['tranche_2'] = montant_tranche_2
            montant_restant -= montant_tranche_2
            infos.append(f"✓ 2ème tranche: {int(montant_tranche_2):,} GNF".replace(',', ' '))
    
    elif has_insc and has_annuel:
        # Frais d'inscription + Paiement annuel complet
        infos.append("🔄 Paiement combiné détecté: Inscription + Annuel")
        
        # Allouer l'inscription
        if inscription_restante > 0:
            montant_inscription = min(FRAIS_INSCRIPTION, inscription_restante, montant_restant)
            allocations['inscription'] = montant_inscription
            montant_restant -= montant_inscription
            infos.append(f"✓ Inscription: {int(montant_inscription):,} GNF".replace(',', ' '))
        
        # Répartir le reste entre les tranches en garantissant 0 reliquat
        if montant_restant > 0:
            total_tranches_restantes = tranche_1_restante + tranche_2_restante + tranche_3_restante

            if total_tranches_restantes > 0:
                # 1) Cas exact: si le montant couvre (quasi) exactement le total restant
                #    on alloue séquentiellement T1 -> T2 -> T3 pour éviter tout arrondi
                if abs(montant_restant - total_tranches_restantes) <= Decimal('1'):
                    # Allocation séquentielle exacte
                    a1 = min(tranche_1_restante, montant_restant)
                    restant_tmp = montant_restant - a1
                    a2 = min(tranche_2_restante, restant_tmp)
                    restant_tmp -= a2
                    a3 = min(tranche_3_restante, restant_tmp)

                    allocations['tranche_1'] = a1
                    allocations['tranche_2'] = a2
                    allocations['tranche_3'] = a3

                    infos.append(f"✓ 1ère tranche: {int(a1):,} GNF".replace(',', ' '))
                    if a2 > 0:
                        infos.append(f"✓ 2ème tranche: {int(a2):,} GNF".replace(',', ' '))
                    if a3 > 0:
                        infos.append(f"✓ 3ème tranche: {int(a3):,} GNF".replace(',', ' '))
                    
                    # tout alloué, ajuster le reliquat interne à 0
                    montant_restant = Decimal('0')
                else:
                    # 2) Cas proportionnel: on arrondit à l'unité GNF et on affecte le reliquat
                    pool = montant_restant
                    a1 = Decimal('0')
                    a2 = Decimal('0')
                    a3 = Decimal('0')

                    if tranche_1_restante > 0 or tranche_2_restante > 0 or tranche_3_restante > 0:
                        # Calcul des parts brutes
                        raw1 = pool * (tranche_1_restante / total_tranches_restantes) if tranche_1_restante > 0 else Decimal('0')
                        raw2 = pool * (tranche_2_restante / total_tranches_restantes) if tranche_2_restante > 0 else Decimal('0')

                        # Arrondir à l'unité GNF (arrondi inférieur via int())
                        a1 = min(tranche_1_restante, Decimal(int(raw1)))
                        a2 = min(tranche_2_restante, Decimal(int(raw2)))
                        # Le reste pour T3
                        a3 = pool - a1 - a2
                        a3 = min(tranche_3_restante, a3)

                        # S'il reste encore du reliquat après plafonnement de T3, le redistribuer
                        residual = pool - (a1 + a2 + a3)
                        # Distribuer 1 GNF par 1 GNF en respectant les plafonds
                        while residual > 0:
                            progressed = False
                            if a1 < tranche_1_restante and residual > 0:
                                a1 += Decimal('1')
                                residual -= Decimal('1')
                                progressed = True
                            if a2 < tranche_2_restante and residual > 0:
                                a2 += Decimal('1')
                                residual -= Decimal('1')
                                progressed = True
                            if a3 < tranche_3_restante and residual > 0:
                                a3 += Decimal('1')
                                residual -= Decimal('1')
                                progressed = True
                            if not progressed:
                                # Plus de capacité sur les tranches, on sort (ne devrait pas arriver)
                                break

                        allocations['tranche_1'] = a1
                        allocations['tranche_2'] = a2
                        allocations['tranche_3'] = a3

                        if a1 > 0:
                            infos.append(f"✓ 1ère tranche: {int(a1):,} GNF".replace(',', ' '))
                        if a2 > 0:
                            infos.append(f"✓ 2ème tranche: {int(a2):,} GNF".replace(',', ' '))
                        if a3 > 0:
                            infos.append(f"✓ 3ème tranche: {int(a3):,} GNF".replace(',', ' '))

                        # Ajuster le reliquat interne en fonction des allocations
                        montant_restant = pool - (a1 + a2 + a3)
    
    else:
        # Type de paiement non explicitement combiné
        if has_insc and has_any_tranche:
            # Cas générique combiné (Inscription + Tranche(s))
            infos.append("🔄 Paiement combiné détecté: Inscription + Tranche(s)")

            # Allouer d'abord l'inscription
            if inscription_restante > 0:
                montant_inscription = min(FRAIS_INSCRIPTION, inscription_restante, montant_restant)
                allocations['inscription'] = montant_inscription
                montant_restant -= montant_inscription
                infos.append(f"✓ Inscription: {int(montant_inscription):,} GNF".replace(',', ' '))

            # Ensuite, répartir séquentiellement T1 -> T2 -> T3
            if montant_restant > 0 and tranche_1_restante > 0:
                montant_tranche_1 = min(tranche_1_restante, montant_restant)
                allocations['tranche_1'] = montant_tranche_1
                montant_restant -= montant_tranche_1
                infos.append(f"✓ 1ère tranche: {int(montant_tranche_1):,} GNF".replace(',', ' '))

            if montant_restant > 0 and tranche_2_restante > 0:
                montant_tranche_2 = min(tranche_2_restante, montant_restant)
                allocations['tranche_2'] = montant_tranche_2
                montant_restant -= montant_tranche_2
                infos.append(f"✓ 2ème tranche: {int(montant_tranche_2):,} GNF".replace(',', ' '))

            if montant_restant > 0 and tranche_3_restante > 0:
                montant_tranche_3 = min(tranche_3_restante, montant_restant)
                allocations['tranche_3'] = montant_tranche_3
                montant_restant -= montant_tranche_3
                infos.append(f"✓ 3ème tranche: {int(montant_tranche_3):,} GNF".replace(',', ' '))
        else:
            # Type non combiné: déléguer à la logique existante avec une cible si identifiable
            cible = _map_type_to_tranche(getattr(paiement.type_paiement, 'nom', ''))
            return _allocate_payment_to_echeancier(echeancier, paiement.montant, paiement.date_paiement, cible)
    
    # Appliquer les allocations à l'échéancier
    if allocations['inscription'] > 0:
        echeancier.frais_inscription_paye = (echeancier.frais_inscription_paye or Decimal('0')) + allocations['inscription']
    
    if allocations['tranche_1'] > 0:
        echeancier.tranche_1_payee = (echeancier.tranche_1_payee or Decimal('0')) + allocations['tranche_1']
    
    if allocations['tranche_2'] > 0:
        echeancier.tranche_2_payee = (echeancier.tranche_2_payee or Decimal('0')) + allocations['tranche_2']
    
    if allocations['tranche_3'] > 0:
        echeancier.tranche_3_payee = (echeancier.tranche_3_payee or Decimal('0')) + allocations['tranche_3']
    
    # Calculer le nouveau solde
    total_du = (echeancier.frais_inscription_du or Decimal('0')) + (echeancier.tranche_1_due or Decimal('0')) + (echeancier.tranche_2_due or Decimal('0')) + (echeancier.tranche_3_due or Decimal('0'))
    total_paye = (echeancier.frais_inscription_paye or Decimal('0')) + (echeancier.tranche_1_payee or Decimal('0')) + (echeancier.tranche_2_payee or Decimal('0')) + (echeancier.tranche_3_payee or Decimal('0'))
    nouveau_solde = total_du - total_paye
    
    # Afficher l'alerte de reliquat uniquement s'il reste effectivement un solde
    if montant_restant > 0 and nouveau_solde > 0:
        warnings.append(f"⚠️ Montant non alloué: {int(montant_restant):,} GNF - Vérifiez les montants dus".replace(',', ' '))

    # Mettre à jour le statut
    if nouveau_solde <= 0:
        echeancier.statut = 'PAYE_COMPLET'
        infos.append("🎉 Échéancier entièrement réglé ! Félicitations.")
    else:
        # Vérifier les retards par rapport à la date du paiement courant
        # (important pour les tests et la cohérence historique)
        now = paiement.date_paiement
        en_retard = (
            (now > echeancier.date_echeance_inscription and echeancier.frais_inscription_paye < echeancier.frais_inscription_du) or
            (now > echeancier.date_echeance_tranche_1 and echeancier.tranche_1_payee < echeancier.tranche_1_due) or
            (now > echeancier.date_echeance_tranche_2 and echeancier.tranche_2_payee < echeancier.tranche_2_due) or
            (now > echeancier.date_echeance_tranche_3 and echeancier.tranche_3_payee < echeancier.tranche_3_due)
        )
        echeancier.statut = 'EN_RETARD' if en_retard else 'PAYE_PARTIEL'
    
    # Sauvegarder l'échéancier
    echeancier.save()
    
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
    now = timezone.now()
    
    # Paiements validés ce mois
    paiements_mois = paiements_qs.filter(
        date_paiement__month=now.month,
        date_paiement__year=now.year,
        statut='VALIDE'
    )
    
    # Paiements validés (tous statuts valides)
    paiements_valides_mois = paiements_qs.filter(
        date_paiement__month=now.month,
        date_paiement__year=now.year
    ).exclude(statut='ANNULE')
    
    # Si pas de paiements ce mois, prendre les paiements récents (30 derniers jours)
    if paiements_valides_mois.count() == 0:
        from datetime import timedelta
        date_limite = now.date() - timedelta(days=30)
        paiements_valides_mois = paiements_qs.filter(
            date_paiement__gte=date_limite
        ).exclude(statut='ANNULE')
    
    # Échéanciers en retard (calculer le solde restant avec annotations)
    from django.db.models import F
    
    # Calculer le solde restant = total_du - total_paye (éviter collision avec @property)
    echeanciers_avec_solde = echeanciers_qs.annotate(
        total_du_calc=F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due'),
        total_paye_calc=F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'),
        solde_calcule=(
            F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due') - (
                F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
            )
        )
    )
    
    # Élèves en retard (solde > 0)
    eleves_retard = echeanciers_avec_solde.filter(
        solde_calcule__gt=0
    ).count()
    
    if eleves_retard == 0:
        eleves_retard = echeanciers_qs.filter(
            statut='EN_RETARD'
        ).count()
    
    stats = {
        'total_paiements_mois': paiements_valides_mois.aggregate(total=Sum('montant'))['total'] or 0,
        'nombre_paiements_mois': paiements_valides_mois.count(),
        'eleves_en_retard': eleves_retard,
        'paiements_en_attente': paiements_qs.filter(statut='EN_ATTENTE').count(),
        
        # Statistiques supplémentaires pour debug
        'total_paiements_systeme': paiements_qs.count(),
        'total_echeanciers': echeanciers_qs.count(),
        'debug_mois': now.month,
        'debug_annee': now.year,
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
@require_http_methods(["POST"])
def relancer_eleve(request, eleve_id):
    """Action simple pour relancer un élève en retard (placeholder).
    Enregistre un message UI et redirige. À étendre avec modèle Relance + envoi réel.
    """
    # Autorisation: admin ou droit de validation paiements (comptable)
    if not (user_is_admin(request.user) or can_validate_payments(request.user)):
        messages.error(request, "Vous n'avez pas l'autorisation pour relancer.")
        return redirect('paiements:tableau_bord')

    # Charger l'échéancier pour vérifier la situation
    eleve = get_object_or_404(Eleve, id=eleve_id)
    try:
        echeancier = eleve.echeancier
    except EcheancierPaiement.DoesNotExist:
        messages.warning(request, "Aucun échéancier pour cet élève: relance non effectuée.")
        return redirect('paiements:echeancier_eleve', eleve_id=eleve.id)

    # Vérifier retard/solde
    total_du = (echeancier.frais_inscription_du or Decimal('0')) + (echeancier.tranche_1_due or Decimal('0')) + (echeancier.tranche_2_due or Decimal('0')) + (echeancier.tranche_3_due or Decimal('0'))
    total_paye = (echeancier.frais_inscription_paye or Decimal('0')) + (echeancier.tranche_1_payee or Decimal('0')) + (echeancier.tranche_2_payee or Decimal('0')) + (echeancier.tranche_3_payee or Decimal('0'))
    solde = total_du - total_paye

    if solde <= 0 and echeancier.statut != 'EN_RETARD':
        messages.info(request, "Échéancier soldé: aucune relance nécessaire.")
    else:
        # Enregistrer une relance (journal)
        contenu = request.POST.get('message') or (
            f"Relance de paiement – Solde restant estimé: {int(solde):,} GNF.".replace(',', ' ')
        )
        canal = (request.POST.get('canal') or 'AUTRE').upper()
        if canal not in dict(Relance.CANAL_CHOICES):
            canal = 'AUTRE'
        Relance.objects.create(
            eleve=eleve,
            canal=canal,
            message=contenu,
            statut='ENREGISTREE',
            solde_estime=solde,
            cree_par=request.user
        )
        messages.success(request, f"Relance enregistrée pour {eleve.nom_complet} (solde: {int(solde):,} GNF)".replace(',', ' '))

    # Redirection: si `next` fourni, y retourner, sinon vers l'échéancier
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('paiements:echeancier_eleve', eleve_id=eleve.id)

@login_required
def liste_relances(request):
    """Historique des relances avec filtres simples et pagination."""
    # Autorisation: admin ou droit de validation paiements (comptable)
    if not (user_is_admin(request.user) or can_validate_payments(request.user)):
        messages.error(request, "Vous n'avez pas l'autorisation pour consulter les relances.")
        return redirect('paiements:tableau_bord')

    relances = Relance.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole', 'cree_par')
    # Filtrer par école pour non-admin
    if not user_is_admin(request.user):
        relances = filter_by_user_school(relances, request.user, 'eleve__classe__ecole')

    # Filtres
    q = (request.GET.get('q') or '').strip()
    canal = (request.GET.get('canal') or '').strip().upper()
    statut = (request.GET.get('statut') or '').strip().upper()
    if q:
        relances = relances.filter(
            Q(eleve__nom__icontains=q) | Q(eleve__prenom__icontains=q) | Q(eleve__matricule__icontains=q) | Q(message__icontains=q)
        )
    if canal and canal in dict(Relance.CANAL_CHOICES):
        relances = relances.filter(canal=canal)
    if statut and statut in dict(Relance.STATUT_CHOICES):
        relances = relances.filter(statut=statut)

    # Pagination
    paginator = Paginator(relances.order_by('-date_creation'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'q': q,
        'canal': canal,
        'statut': statut,
        'titre_page': 'Historique des relances',
    }
    return render(request, 'paiements/relances.html', context)

@login_required
def ajax_statistiques_paiements(request):
    """Vue AJAX pour récupérer les statistiques des paiements"""
    try:
        # Base querysets filtrés par école si non-admin
        paiements_qs = Paiement.objects.all()
        echeanciers_qs = EcheancierPaiement.objects.all()
        if not user_is_admin(request.user):
            paiements_qs = filter_by_user_school(paiements_qs, request.user, 'eleve__classe__ecole')
            echeanciers_qs = filter_by_user_school(echeanciers_qs, request.user, 'eleve__classe__ecole')

        # Statistiques générales (même logique que tableau_bord_paiements)
        now = timezone.now()
        
        # Paiements validés (tous statuts valides)
        paiements_valides_mois = paiements_qs.filter(
            date_paiement__month=now.month,
            date_paiement__year=now.year
        ).exclude(statut='ANNULE')
        
        # Si pas de paiements ce mois, prendre les paiements récents (30 derniers jours)
        if paiements_valides_mois.count() == 0:
            from datetime import timedelta
            date_limite = now.date() - timedelta(days=30)
            paiements_valides_mois = paiements_qs.filter(
                date_paiement__gte=date_limite
            ).exclude(statut='ANNULE')
        
        # Échéanciers en retard (calculer le solde restant avec annotations)
        from django.db.models import F
        
        # Calculer le solde restant avec aliases *_calc pour éviter collision avec @property
        echeanciers_avec_solde = echeanciers_qs.annotate(
            total_du_calc=F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due'),
            total_paye_calc=F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'),
            solde_calcule=(
                F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due') - (
                    F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
                )
            )
        )
        
        # Élèves en retard (solde > 0)
        eleves_retard = echeanciers_avec_solde.filter(
            solde_calcule__gt=0
        ).count()
        
        if eleves_retard == 0:
            eleves_retard = echeanciers_qs.filter(
                statut='EN_RETARD'
            ).count()
        
        stats = {
            'total_paiements_mois': float(paiements_valides_mois.aggregate(total=Sum('montant'))['total'] or 0),
            'nombre_paiements_mois': paiements_valides_mois.count(),
            'eleves_en_retard': eleves_retard,
            'paiements_en_attente': paiements_qs.filter(statut='EN_ATTENTE').count(),
        }
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def liste_paiements(request):
    """Liste de tous les paiements avec une zone de recherche multi-critères (classe, école, nom, prénoms, type, mode, n° reçu, matricule, statut)."""
    # Gestion d'export direct via ?export=excel|pdf vers "tranches par classe"
    export = (request.GET.get('export') or '').strip().lower()
    if export in {'excel', 'pdf'}:
        from django.urls import reverse
        base_name = 'paiements:export_tranches_par_classe_excel' if export == 'excel' else 'paiements:export_tranches_par_classe_pdf'
        url = reverse(base_name)
        # Conserver certains filtres si fournis
        params = {}
        for key in ['ecole', 'classe', 'classe_id', 'annee_scolaire']:
            val = request.GET.get(key)
            if val:
                params[key] = val
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"
        return redirect(url)
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
    paiements_valides = paiements.exclude(statut='ANNULE')
    totaux = {
        'total_paiements': paiements.count(),  # nombre total affiché (inclut tous statuts)
        'montant_total': paiements_valides.aggregate(total=Sum('montant'))['total'] or 0,  # exclut les annulés
        'total_en_attente': paiements.filter(statut='EN_ATTENTE').count(),
        'montant_en_attente': paiements.filter(statut='EN_ATTENTE').aggregate(total=Sum('montant'))['total'] or 0,
    }
    
    # Totaux ce mois (sur les paiements filtrés)
    current_month = datetime.now().month
    current_year = datetime.now().year
    paiements_ce_mois = paiements_valides.filter(
        date_paiement__month=current_month,
        date_paiement__year=current_year
    )
    
    totaux.update({
        'total_ce_mois': paiements_ce_mois.count(),
        'montant_ce_mois': paiements_ce_mois.aggregate(total=Sum('montant'))['total'] or 0,
    })
    
    # Calcul du nombre d'élèves à relancer (en retard / solde > 0)
    from django.db.models import F
    echeanciers_qs = EcheancierPaiement.objects.all()
    if not user_is_admin(request.user):
        echeanciers_qs = filter_by_user_school(echeanciers_qs, request.user, 'eleve__classe__ecole')
    echeanciers_avec_solde = echeanciers_qs.annotate(
        total_du_calc=F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due'),
        total_paye_calc=F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'),
        solde_calcule=(
            F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due') - (
                F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee')
            )
        )
    )
    eleves_retard = echeanciers_avec_solde.filter(solde_calcule__gt=0).count()
    if eleves_retard == 0:
        eleves_retard = echeanciers_qs.filter(statut='EN_RETARD').count()

    # Pagination
    paginator = Paginator(paiements, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'totaux': totaux,
        'titre_page': 'Liste des Paiements',
        'q': q,
        'eleves_en_retard': eleves_retard,
    }
    
    # Si requête AJAX, renvoyer uniquement le fragment (totaux + tableau + pagination)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'paiements/_paiements_resultats.html', context)

    return render(request, 'paiements/liste_paiements.html', context)

@login_required
def ajax_classes_par_ecole(request):
    """Retourne en JSON la liste des classes filtrées par école et année scolaire.
    Respecte les permissions: un non-admin ne voit que les classes de son/ses école(s).
    Params (GET): ecole_id (optionnel), annee (optionnel)
    """
    try:
        ecole_id = (request.GET.get('ecole_id') or '').strip()
        annee = (request.GET.get('annee') or '').strip()

        classes = Classe.objects.select_related('ecole').all()
        # Restriction par école pour non-admin
        if not user_is_admin(request.user):
            classes = filter_by_user_school(classes, request.user, 'ecole')

        if ecole_id:
            classes = classes.filter(ecole_id=ecole_id)
        if annee:
            classes = classes.filter(annee_scolaire=annee)

        classes = classes.order_by('nom')
        data = [
            {
                'id': c.id,
                'nom': c.nom,
                'ecole_nom': c.ecole.nom,
            }
            for c in classes[:500]
        ]
        return JsonResponse({'success': True, 'classes': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def export_liste_paiements_excel(request):
    """Export Excel de la liste des paiements (selon le filtre q), avec colonne Tranche.

    Colonnes: Élève, Classe, École, Tranche, Montant, Mode, Date, Statut, N° Reçu.
    Respecte la séparation par école pour les non-admins.
    """
    # Contrôle d'accès similaire aux exports: Admin ou Comptable
    is_admin = user_is_admin(request.user)
    is_comptable = False
    try:
        if hasattr(request.user, 'profil'):
            is_comptable = (getattr(request.user.profil, 'role', None) == 'COMPTABLE')
    except Exception:
        is_comptable = False
    if not (is_admin or is_comptable):
        # On autorise aussi la simple consultation export pour les utilisateurs de l'école
        # mais on filtre strictement leur école. Ici on n'interdit pas, on continue.
        pass

    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except Exception:
        return HttpResponse("OpenPyXL n'est pas installé. Veuillez exécuter: pip install openpyxl", status=500)

    paiements = Paiement.objects.select_related(
        'eleve', 'type_paiement', 'mode_paiement', 'eleve__classe', 'eleve__classe__ecole'
    ).order_by('-date_paiement')

    # Restriction école pour non-admin
    if not user_is_admin(request.user):
        paiements = filter_by_user_school(paiements, request.user, 'eleve__classe__ecole')

    # Réappliquer le même filtre libre 'q' que la vue liste
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
        statut_map = {
            'valide': 'VALIDE', 'validé': 'VALIDE', 'ok': 'VALIDE',
            'attente': 'EN_ATTENTE', 'en attente': 'EN_ATTENTE', 'pending': 'EN_ATTENTE',
            'rejete': 'REJETE', 'rejeté': 'REJETE',
            'annule': 'ANNULE', 'annulé': 'ANNULE', 'annulee': 'ANNULE', 'annulée': 'ANNULE'
        }
        for key, code in statut_map.items():
            if key in q_lower:
                filtres = filtres | Q(statut=code)
        paiements = paiements.filter(filtres)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Paiements'
    headers = ['Élève', 'Classe', 'École', 'Tranche', 'Montant (GNF)', 'Mode', 'Date', 'Statut', 'N° Reçu']
    ws.append(headers)

    for p in paiements[:20000]:  # garde-fou
        eleve_nom = getattr(p.eleve, 'nom_complet', f"{getattr(p.eleve, 'prenom', '')} {getattr(p.eleve, 'nom', '')}".strip())
        classe_nom = getattr(p.eleve.classe, 'nom', '') if getattr(p.eleve, 'classe', None) else ''
        ecole_nom = getattr(p.eleve.classe.ecole, 'nom', '') if getattr(p.eleve, 'classe', None) else ''
        tranche = getattr(p.type_paiement, 'nom', '')  # Utilisé comme colonne Tranche
        montant = int(p.montant or 0)
        mode = getattr(p.mode_paiement, 'nom', '')
        date_str = p.date_paiement.strftime('%d/%m/%Y') if getattr(p, 'date_paiement', None) else ''
        statut = p.get_statut_display() if hasattr(p, 'get_statut_display') else p.statut
        ws.append([eleve_nom, classe_nom, ecole_nom, tranche, montant, mode, date_str, statut, p.numero_recu])

    # Largeurs colonnes simples
    widths = [28, 16, 22, 18, 18, 16, 14, 14, 16]
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = w

    from io import BytesIO
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    resp = HttpResponse(stream.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    suffix = datetime.now().strftime('%Y%m%d')
    filename = f'paiements_liste_{suffix}.xlsx'
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

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
@can_add_payments
def ajouter_paiement(request, eleve_id=None):
    """Ajouter un nouveau paiement"""
    eleve = None
    if eleve_id:
        eleves_qs = Eleve.objects.select_related('classe', 'classe__ecole').prefetch_related('echeancier')
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
                if (montant_saisi is not None) and (montant_saisi > 0) and (montant_saisi > solde):
                    form.add_error('montant', f"Le montant saisi dépasse le reste à payer ({int(solde):,} GNF).".replace(',', ' '))
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

            # Appliquer une remise si saisie par le comptable (réduction directe du montant)
            remise_pct = form.cleaned_data.get('remise_pourcentage') or Decimal('0')
            montant_original = paiement.montant or Decimal('0')
            montant_remise = Decimal('0')
            if remise_pct and remise_pct > 0 and montant_original > 0:
                try:
                    # Calculer la remise
                    montant_remise = (montant_original * Decimal(remise_pct)) / Decimal('100')
                    # Cap au montant original
                    if montant_remise > montant_original:
                        montant_remise = montant_original
                    # Déduire du montant du paiement
                    paiement.montant = max(Decimal('0'), montant_original - montant_remise)
                except Exception:
                    # En cas d'erreur de conversion/calcul, ignorer la remise
                    montant_remise = Decimal('0')

            # Le numéro de reçu est maintenant généré automatiquement par le modèle
            try:
                paiement.save()
            except ValueError as e:
                messages.error(request, f"Erreur lors de la génération du numéro de reçu: {e}")
                context = {
                    'form': form,
                    'eleve': eleve_cible if eleve is None else eleve,
                    'titre_page': 'Nouveau Paiement',
                    'action': 'Ajouter'
                }
                return render(request, 'paiements/form_paiement.html', context)

            # Enregistrer la ligne de remise appliquée (si applicable)
            try:
                if montant_remise and montant_remise > 0:
                    # Chercher/créer une RemiseReduction générique "Remise manuelle"
                    from django.utils.timezone import now
                    today = now().date()
                    remise_obj, _ = RemiseReduction.objects.get_or_create(
                        nom='Remise manuelle',
                        type_remise='POURCENTAGE',
                        valeur=Decimal(remise_pct or 0),
                        motif='AUTRE',
                        defaults={
                            'description': 'Remise saisie manuellement lors de la création du paiement',
                            'date_debut': today,
                            'date_fin': today,
                            'actif': True,
                            'cree_par': request.user if request.user.is_authenticated else None,
                        }
                    )
                    # Si la remise existe mais hors validité aujourd'hui, on force une validité du jour
                    if not (remise_obj.date_debut <= today <= remise_obj.date_fin):
                        remise_obj.date_debut = today
                        remise_obj.date_fin = today
                        remise_obj.actif = True
                        remise_obj.save(update_fields=['date_debut', 'date_fin', 'actif'])

                    PaiementRemise.objects.update_or_create(
                        paiement=paiement,
                        remise=remise_obj,
                        defaults={'montant_remise': montant_remise}
                    )
                    # Info utilisateur
                    messages.info(request, f"Remise appliquée: {int(montant_remise):,} GNF (\u2212{remise_pct}% )".replace(',', ' '))
            except Exception as _e:
                # Ne pas bloquer le flux si la ligne de remise échoue
                messages.warning(request, "La remise n'a pas pu être enregistrée en détail, mais le paiement a bien été créé.")

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
        # Définir la date du jour par défaut pour le champ date_paiement
        form.fields['date_paiement'].initial = timezone.now().date()
    
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
@can_validate_payments
def valider_paiement(request, paiement_id):
    """Valider un paiement en attente"""
    if request.method == 'POST':
        qs = Paiement.objects.all()
        if not user_is_admin(request.user):
            qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')
        paiement = get_object_or_404(qs, id=paiement_id)
        
        if paiement.statut == 'EN_ATTENTE':
            # 1) Exécuter l'allocation D'ABORD dans une transaction
            try:
                with transaction.atomic():
                    try:
                        echeancier = paiement.eleve.echeancier
                    except EcheancierPaiement.DoesNotExist:
                        messages.info(request, "Aucun échéancier n'existe pour cet élève. Veuillez le créer pour refléter ce paiement dans les tranches.")
                        return redirect('paiements:detail_paiement', paiement_id=paiement_id)

                    feedback = _allocate_combined_payment(paiement, echeancier)

                    # Détecter les erreurs bloquantes (surpaiements)
                    blocking_errors = [w for w in feedback.get('warnings', []) if isinstance(w, str) and w.strip().upper().startswith('ERREUR')]
                    if blocking_errors:
                        # Annuler l'allocation via rollback transactionnel
                        for w in blocking_errors:
                            messages.error(request, w)
                        # Conserver aussi les autres infos utiles
                        for w in feedback.get('warnings', []):
                            if w not in blocking_errors:
                                messages.warning(request, w)
                        for info in feedback.get('info', []):
                            messages.info(request, info)
                        # Déclencher un rollback explicite en levant une exception
                        raise IntegrityError("Blocking validation error: overpayment detected")

                    # Pas d'erreur bloquante: commit de l'allocation et validation du paiement
                    paiement.statut = 'VALIDE'
                    paiement.valide_par = request.user
                    paiement.date_validation = timezone.now()
                    paiement.save()

                    # Afficher les messages non bloquants
                    for w in feedback.get('warnings', []):
                        messages.warning(request, w)
                    for info in feedback.get('info', []):
                        messages.info(request, info)

            except IntegrityError:
                # Transaction annulée: le paiement reste EN_ATTENTE
                return redirect('paiements:detail_paiement', paiement_id=paiement_id)

            messages.success(request, f"Paiement #{paiement.numero_recu} validé avec succès.")
        else:
            messages.error(request, "Ce paiement ne peut pas être validé.")
    
    return redirect('paiements:detail_paiement', paiement_id=paiement_id)

@login_required
@vary_on_cookie
@cache_page(60 * 10)
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
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from django.utils.formats import number_format
        from django.utils.timezone import localtime
        from django.contrib.staticfiles import finders
    except Exception:
        messages.error(request, "La génération de PDF nécessite la bibliothèque ReportLab. Veuillez l'installer (pip install reportlab).")
        return redirect('paiements:detail_paiement', paiement_id=paiement.id)

    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    
    # Améliorer la qualité de rendu des polices
    c.setPageCompression(1)  # Activer la compression pour de meilleurs résultats
    
    # Enregistrer des polices système pour une meilleure qualité
    try:
        # Essayer d'utiliser des polices système plus nettes et modernes
        import platform
        if platform.system() == "Windows":
            # Polices Windows modernes - Calibri pour une meilleure lisibilité
            calibri_path = "C:/Windows/Fonts/calibri.ttf"
            calibri_bold_path = "C:/Windows/Fonts/calibrib.ttf"
            # Fallback vers Arial si Calibri n'est pas disponible
            arial_path = "C:/Windows/Fonts/arial.ttf"
            arial_bold_path = "C:/Windows/Fonts/arialbd.ttf"
            
            if os.path.exists(calibri_path):
                pdfmetrics.registerFont(TTFont('Calibri', calibri_path))
                pdfmetrics.registerFont(TTFont('MainFont', calibri_path))
            elif os.path.exists(arial_path):
                pdfmetrics.registerFont(TTFont('Arial', arial_path))
                pdfmetrics.registerFont(TTFont('MainFont', arial_path))
                
            if os.path.exists(calibri_bold_path):
                pdfmetrics.registerFont(TTFont('Calibri-Bold', calibri_bold_path))
                pdfmetrics.registerFont(TTFont('MainFont-Bold', calibri_bold_path))
            elif os.path.exists(arial_bold_path):
                pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
                pdfmetrics.registerFont(TTFont('MainFont-Bold', arial_bold_path))
    except Exception:
        # Fallback vers les polices par défaut si erreur
        pass
    
    # Marges
    margin_x = 20 * mm
    margin_y = 20 * mm

    # Filigrane avec logo de l'école (même style que fiche d'inscription)
    # Standardisation filigrane: logo centré, rotation 30°, opacité 4%
    draw_logo_watermark(c, width, height, opacity=0.04, rotate=30, scale=1.5)

    # Résolution du chemin du logo pour l'en-tête
    logo_path = None
    try:
        logo_path = finders.find('logos/logo.png')
    except Exception:
        pass
    if not logo_path:
        try:
            from django.conf import settings
            candidate = os.path.join(getattr(settings, 'BASE_DIR', ''), 'static', 'logos', 'logo.png')
            if candidate and os.path.exists(candidate):
                logo_path = candidate
        except Exception:
            pass

    # En-tête avec logo + titre (ajusté pour éviter chevauchement avec photo élève)
    c.saveState()
    try:
        if logo_path:
            c.drawImage(logo_path, margin_x, height - margin_y - 30, width=60, height=30, preserveAspectRatio=True, mask='auto')
        c.setFillColor(colors.HexColor('#0056b3'))
        try:
            c.setFont("MainFont-Bold", 18)
        except:
            c.setFont("Helvetica-Bold", 18)
        
        # Centrer le nom de l'école avec taille réduite
        text = "École Moderne HADJA KANFING DIANÉ"
        text_width = c.stringWidth(text, "MainFont-Bold", 18) if "MainFont-Bold" in c.getAvailableFonts() else c.stringWidth(text, "Helvetica-Bold", 18)
        c.drawString((width - text_width) / 2, height - margin_y - 10, text)
        
        c.setFillColor(colors.black)
        try:
            c.setFont("MainFont-Bold", 18)
        except:
            c.setFont("Helvetica-Bold", 18)
        
        # Centrer le titre du reçu
        text = f"REÇU DE PAIEMENT N° {paiement.numero_recu}"
        text_width = c.stringWidth(text, "MainFont-Bold", 18) if "MainFont-Bold" in c.getAvailableFonts() else c.stringWidth(text, "Helvetica-Bold", 18)
        c.drawString((width - text_width) / 2, height - margin_y - 28, text)
        # Ligne de séparation
        c.setStrokeColor(colors.HexColor('#0056b3'))
        c.setLineWidth(1)
        c.line(margin_x, height - margin_y - 38, width - margin_x, height - margin_y - 38)
    finally:
        c.restoreState()

    # Photo de l'élève (en haut à droite, bien positionnée)
    photo_displayed = False
    try:
        if getattr(paiement.eleve, 'photo', None) and paiement.eleve.photo.name:
            eleve_photo_path = paiement.eleve.photo.path  # chemin fichier local
            photo_box = 35 * mm  # taille carrée agrandie ~35mm
            photo_x = width - margin_x - photo_box - 5  # 5mm de marge du bord
            photo_y = height - margin_y - 120 - photo_box  # descendue encore plus bas (120mm au lieu de 80mm)
            
            # Cadre autour de la photo
            c.setStrokeColor(colors.HexColor('#0056b3'))
            c.setLineWidth(1)
            c.rect(photo_x - 2, photo_y - 2, photo_box + 4, photo_box + 4)
            
            c.drawImage(
                eleve_photo_path,
                photo_x,
                photo_y,
                width=photo_box,
                height=photo_box,
                preserveAspectRatio=True,
                mask='auto'
            )
            photo_displayed = True
    except Exception:
        # Si l'image n'est pas disponible ou invalide, on ignore sans bloquer la génération du PDF
        pass
    
    # Si pas de photo, afficher un placeholder
    if not photo_displayed:
        photo_box = 35 * mm
        photo_x = width - margin_x - photo_box - 5
        photo_y = height - margin_y - 120 - photo_box  # même position que la vraie photo
        
        # Cadre pour placeholder
        c.setStrokeColor(colors.lightgrey)
        c.setFillColor(colors.lightgrey)
        c.setLineWidth(1)
        c.rect(photo_x, photo_y, photo_box, photo_box, fill=1, stroke=1)
        
        # Texte "Photo" centré
        c.setFillColor(colors.darkgrey)
        try:
            c.setFont("MainFont", 12)
        except:
            c.setFont("Helvetica", 12)
        text = "Photo"
        text_width = c.stringWidth(text, "MainFont", 12) if "MainFont" in c.getAvailableFonts() else c.stringWidth(text, "Helvetica", 12)
        c.drawString(photo_x + (photo_box - text_width) / 2, photo_y + photo_box / 2 - 5, text)

    # Informations élève et paiement (ajusté pour éviter chevauchement avec photo)
    y = height - margin_y - 70  # Descendre un peu plus pour laisser place à la photo agrandie
    try:
        c.setFont("MainFont", 14)
    except:
        c.setFont("Helvetica", 14)

    def line(label, value):
        nonlocal y
        try:
            c.setFont("MainFont-Bold", 14)
        except:
            c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_x, y, f"{label} :")
        try:
            c.setFont("MainFont", 14)
        except:
            c.setFont("Helvetica", 14)
        c.drawString(margin_x + 140, y, str(value))
        y -= 20

    # Formatage
    # Arrondi pour l'affichage du montant au millier le plus proche
    try:
        from decimal import Decimal as _Dec
        _mdec = _Dec(paiement.montant or 0)
        _mdisp = ((_mdec + _Dec('500')) // _Dec('1000')) * _Dec('1000')
        montant_fmt = f"{int(_mdisp):,}".replace(',', ' ')
    except Exception:
        montant_fmt = f"{int(paiement.montant):,}".replace(',', ' ')
    date_pay = localtime(paiement.date_validation).strftime('%d/%m/%Y %H:%M') if paiement.date_validation else paiement.date_paiement.strftime('%d/%m/%Y')

    line("Élève", f"{paiement.eleve.prenom} {paiement.eleve.nom} (Mat: {paiement.eleve.matricule})")
    line("Classe", f"{paiement.eleve.classe.nom} - {paiement.eleve.classe.ecole.nom}")
    try:
        annee_sco = getattr(paiement.eleve.classe, 'annee_scolaire', '') or ''
        if annee_sco:
            line("Année scolaire", annee_sco)
    except Exception:
        pass
    line("Date de paiement", date_pay)
    line("Type de paiement", paiement.type_paiement.nom)
    line("Mode de paiement", paiement.mode_paiement.nom)
    
    # (Supprimé) Ligne d'échéance sur le reçu PDF pour éviter de masquer la photo
    # Ancien affichage de l'échéance retiré volontairement.
    line("Montant", f"{montant_fmt} GNF")
    line("Statut", paiement.get_statut_display())
    if paiement.reference_externe:
        line("Référence", paiement.reference_externe)

    # Remises appliquées (affichage PDF)
    try:
        remises_qs = list(paiement.remises.select_related('remise').all())
    except Exception:
        remises_qs = []
    if remises_qs:
        y -= 6
        try:
            c.setFont("MainFont-Bold", 14)
        except:
            c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_x, y, "Remises appliquées :")
        y -= 16
        try:
            c.setFont("MainFont", 13)
        except:
            c.setFont("Helvetica", 13)
        total_remise = Decimal('0')
        for pr in remises_qs:
            montant = pr.montant_remise or Decimal('0')
            # Arrondi d'affichage au millier inférieur (visuel uniquement)
            try:
                montant_disp = (montant // Decimal('1000')) * Decimal('1000')
            except Exception:
                montant_disp = montant
            total_remise += montant
            # Nom de la remise
            c.drawString(margin_x, y, f"- {getattr(pr.remise, 'nom', 'Remise')}")
            # Montant (en vert, négatif)
            try:
                c.setFont("MainFont", 13)
            except:
                c.setFont("Helvetica", 13)
            c.setFillColor(colors.HexColor('#198754'))  # vert type "success"
            montant_txt = f"-{int(montant_disp):,}".replace(',', ' ') + " GNF"
            c.drawString(margin_x + 320, y, montant_txt)
            c.setFillColor(colors.black)
            y -= 16
        # Note explicative courte
        y -= 4
        try:
            c.setFont("MainFont", 11)
        except:
            c.setFont("Helvetica", 11)
        c.setFillColor(colors.grey)
        c.drawString(margin_x, y, "Les remises correspondent aux réductions accordées sur ce paiement.")
        c.setFillColor(colors.black)
        y -= 14

    # Observations
    if paiement.observations:
        y -= 6
        try:
            c.setFont("MainFont-Bold", 14)
        except:
            c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_x, y, "Observations :")
        y -= 16
        try:
            c.setFont("MainFont", 13)
        except:
            c.setFont("Helvetica", 13)
        lines = str(paiement.observations).split('\n')
        text_obj = c.beginText(margin_x, y)
        text_obj.setLeading(18)
        for part in lines:
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

        # Par défaut: utiliser les champs stockés de l'échéancier
        paye_insc = echeancier.frais_inscription_paye or Decimal('0')
        paye_t1 = echeancier.tranche_1_payee or Decimal('0')
        paye_t2 = echeancier.tranche_2_payee or Decimal('0')
        paye_t3 = echeancier.tranche_3_payee or Decimal('0')

        # Fallback: si rien n'est payé dans l'échéancier mais qu'il existe des paiements validés,
        # recalculer un instantané en simulant l'allocation de tous les paiements validés.
        if (paye_insc + paye_t1 + paye_t2 + paye_t3) == 0:
            try:
                # Récupérer paiements validés de l'élève, triés par date
                pay_qs = paiement.eleve.paiements.filter(statut='VALIDE').order_by('date_paiement', 'id').select_related('type_paiement')

                # Instantané des montants payés (sans toucher à la DB)
                snap = {
                    'insc_due': echeancier.frais_inscription_du or Decimal('0'),
                    't1_due': echeancier.tranche_1_due or Decimal('0'),
                    't2_due': echeancier.tranche_2_due or Decimal('0'),
                    't3_due': echeancier.tranche_3_due or Decimal('0'),
                    'insc_paye': Decimal('0'),
                    't1_paye': Decimal('0'),
                    't2_paye': Decimal('0'),
                    't3_paye': Decimal('0'),
                }

                def alloc_once(amount: Decimal, cible: str | None):
                    ordre = ['inscription', 't1', 't2', 't3']
                    if cible in ordre:
                        ordre = [cible] + [x for x in ordre if x != cible]
                    restant_loc = Decimal(amount)
                    for key in ordre:
                        if restant_loc <= 0:
                            break
                        if key == 'inscription':
                            due = snap['insc_due']; paid = snap['insc_paye']
                        elif key == 't1':
                            due = snap['t1_due']; paid = snap['t1_paye']
                        elif key == 't2':
                            due = snap['t2_due']; paid = snap['t2_paye']
                        else:
                            due = snap['t3_due']; paid = snap['t3_paye']
                        to_pay = max(Decimal('0'), due - paid)
                        if to_pay <= 0:
                            continue
                        pay_now = min(to_pay, restant_loc)
                        restant_loc -= pay_now
                        if key == 'inscription':
                            snap['insc_paye'] = paid + pay_now
                        elif key == 't1':
                            snap['t1_paye'] = paid + pay_now
                        elif key == 't2':
                            snap['t2_paye'] = paid + pay_now
                        else:
                            snap['t3_paye'] = paid + pay_now

                for p in pay_qs:
                    cible = _map_type_to_tranche(getattr(p.type_paiement, 'nom', ''))
                    alloc_once(Decimal(p.montant), cible)

                paye_insc, paye_t1, paye_t2, paye_t3 = snap['insc_paye'], snap['t1_paye'], snap['t2_paye'], snap['t3_paye']
            except Exception:
                pass

        total_paye = paye_insc + paye_t1 + paye_t2 + paye_t3
        reste = max(Decimal('0'), total_a_payer - total_paye)

        # Ajustements d'affichage: arrondir les restes de tranches au millier inférieur
        due_insc = echeancier.frais_inscription_du or Decimal('0')
        due_t1 = echeancier.tranche_1_due or Decimal('0')
        due_t2 = echeancier.tranche_2_due or Decimal('0')
        due_t3 = echeancier.tranche_3_due or Decimal('0')

        rest_insc = max(Decimal('0'), due_insc - (paye_insc or Decimal('0')))
        rest_t1 = max(Decimal('0'), due_t1 - (paye_t1 or Decimal('0')))
        rest_t2 = max(Decimal('0'), due_t2 - (paye_t2 or Decimal('0')))
        rest_t3 = max(Decimal('0'), due_t3 - (paye_t3 or Decimal('0')))

        def _round_down_1000(x: Decimal) -> Decimal:
            try:
                return (x // Decimal('1000')) * Decimal('1000')
            except Exception:
                return x

        rest_insc_disp = _round_down_1000(rest_insc)
        rest_t1_disp = _round_down_1000(rest_t1)
        rest_t2_disp = _round_down_1000(rest_t2)
        rest_t3_disp = _round_down_1000(rest_t3)

        # Reste à payer affiché = somme des restes arrondis par tranche
        reste_affiche = rest_insc_disp + rest_t1_disp + rest_t2_disp + rest_t3_disp
        # Si tout est réglé (aucun reste réel), forcer l'affichage à 0
        if (rest_insc + rest_t1 + rest_t2 + rest_t3) == 0:
            reste_affiche = Decimal('0')
        
        # Cas soldé via statut/solde (inclut remises): si echeancier indique PAYE_COMPLET ou solde <= 0
        try:
            statut_ech = getattr(echeancier, 'statut', '') or ''
            solde_ech = getattr(echeancier, 'solde_restant', Decimal('0'))
        except Exception:
            statut_ech = ''
            solde_ech = Decimal('0')

        # Si le reste global est 0 OU statut/solde indique un soldé (y compris via remises),
        # afficher 0 pour chaque tranche pour éviter des reliquats visuels
        if (reste_affiche == 0 or reste == 0) or (str(statut_ech) == 'PAYE_COMPLET' or (solde_ech is not None and solde_ech <= 0)):
            rest_insc_disp = rest_t1_disp = rest_t2_disp = rest_t3_disp = Decimal('0')
            reste_affiche = Decimal('0')

        # Ajuster l'affichage du "Déjà payé" pour absorber les écarts d'arrondi
        # Objectif: Total à payer - Reste à payer (affiché) == Déjà payé (affiché)
        total_paye_affiche = total_paye
        try:
            calc_from_reste = total_a_payer - reste_affiche
            ecart = calc_from_reste - total_paye
            # Si l'écart est un petit reliquat (par ex. < 1000 GNF), on ajuste
            if abs(int(ecart)) < 1000:
                total_paye_affiche = calc_from_reste
        except Exception:
            total_paye_affiche = total_paye

        def _round_nearest_1000(x):
            try:
                x = _Dec(x)
                return ((x + _Dec('500')) // _Dec('1000')) * _Dec('1000')
            except Exception:
                return x

        def fmt_money(d):
            try:
                return f"{int(_round_nearest_1000(_Dec(d))):,}".replace(',', ' ') + " GNF"
            except Exception:
                return f"{int(d):,}".replace(',', ' ') + " GNF"

        y -= 10
        try:
            c.setFont("MainFont-Bold", 15)
        except:
            c.setFont("Helvetica-Bold", 15)
        c.drawString(margin_x, y, "Résumé de l'échéancier")
        y -= 20
        try:
            c.setFont("MainFont", 14)
        except:
            c.setFont("Helvetica", 14)
        # Helper: aligner les montants à droite pour éviter le chevauchement avec les libellés longs
        def line_right(label, value_str):
            nonlocal y
            # Libellé à gauche
            try:
                c.setFont("MainFont-Bold", 14)
                font_label = "MainFont-Bold"
            except:
                c.setFont("Helvetica-Bold", 14)
                font_label = "Helvetica-Bold"
            c.drawString(margin_x, y, f"{label} :")
            # Valeur à droite
            try:
                c.setFont("MainFont", 14)
                font_val = "MainFont"
            except:
                c.setFont("Helvetica", 14)
                font_val = "Helvetica"
            val = str(value_str)
            val_w = c.stringWidth(val, font_val, 14)
            x_val = max(margin_x + 150, (c._pagesize[0] - margin_x - val_w))
            c.drawString(x_val, y, val)
            y -= 20

        line_right("Total à payer", fmt_money(total_a_payer))
        line_right("Déjà payé", fmt_money(total_paye_affiche))
        line_right("Reste à payer", fmt_money(reste_affiche))
        # Affichage explicite de la scolarité annuelle (hors inscription)
        scolarite_annuelle_due = (due_t1 + due_t2 + due_t3)
        line_right("Scolarité annuelle (hors inscription)", fmt_money(scolarite_annuelle_due))

        # Détail par tranche
        y -= 4
        try:
            c.setFont("MainFont-Bold", 14)
        except:
            c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_x, y, "Détail des tranches :")
        y -= 18
        try:
            c.setFont("Arial", 13)
        except:
            c.setFont("Helvetica", 13)
        detail = [
            ("Inscription", due_insc, paye_insc, rest_insc_disp),
            ("Tranche 1", due_t1, paye_t1, rest_t1_disp),
            ("Tranche 2", due_t2, paye_t2, rest_t2_disp),
            ("Tranche 3", due_t3, paye_t3, rest_t3_disp),
        ]
        for label, due, paid, rest_disp in detail:
            c.drawString(margin_x, y, f"{label} : dû {fmt_money(due)} | payé {fmt_money(paid)} | reste {fmt_money(rest_disp)}")
            y -= 16
    except EcheancierPaiement.DoesNotExist:
        y -= 10
        try:
            c.setFont("MainFont", 12)
        except:
            c.setFont("Helvetica-Oblique", 12)
        c.drawString(margin_x, y, "Aucun échéancier n'est associé à cet élève.")

    # Pied de page centré
    try:
        c.setFont("MainFont", 10)
    except:
        c.setFont("Helvetica", 10)
    c.setFillColor(colors.grey)
    
    from django.utils import timezone
    text = f"Reçu généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}"
    text_width = c.stringWidth(text, "MainFont", 10) if "MainFont" in c.getAvailableFonts() else c.stringWidth(text, "Helvetica", 10)
    c.drawString((width - text_width) / 2, margin_y + 15, text)
    
    text = "Système de Gestion Scolaire - École Moderne HADJA KANFING DIANÉ"
    text_width = c.stringWidth(text, "MainFont", 10) if "MainFont" in c.getAvailableFonts() else c.stringWidth(text, "Helvetica", 10)
    c.drawString((width - text_width) / 2, margin_y, text)

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


@login_required
@require_http_methods(["GET"])
def ajax_eleve_info(request):
    """Vue AJAX pour récupérer les informations d'un élève par matricule"""
    matricule = request.GET.get('matricule', '').strip()
    
    if not matricule:
        return JsonResponse({'success': False, 'error': 'Matricule requis'})
    
    try:
        # Filtrer selon les permissions utilisateur
        qs = Eleve.objects.select_related('classe', 'classe__ecole')
        if not user_is_admin(request.user):
            qs = filter_by_user_school(qs, request.user, 'classe__ecole')
        
        eleve = qs.get(matricule__iexact=matricule)
        
        # Récupérer l'échéancier s'il existe
        echeancier = None
        try:
            echeancier = eleve.echeancier
        except:
            pass
        
        # Calculer les montants dus et payés
        montants_info = {}
        if echeancier:
            montants_info = {
                'inscription_du': float(echeancier.frais_inscription_du or 0),
                'inscription_paye': float(echeancier.frais_inscription_paye or 0),
                'tranche_1_du': float(echeancier.tranche_1_due or 0),
                'tranche_1_paye': float(echeancier.tranche_1_payee or 0),
                'tranche_2_du': float(echeancier.tranche_2_due or 0),
                'tranche_2_paye': float(echeancier.tranche_2_payee or 0),
                'tranche_3_du': float(echeancier.tranche_3_due or 0),
                'tranche_3_paye': float(echeancier.tranche_3_payee or 0),
                'total_du': float((echeancier.frais_inscription_du or 0) + 
                                (echeancier.tranche_1_due or 0) + 
                                (echeancier.tranche_2_due or 0) + 
                                (echeancier.tranche_3_due or 0)),
                'total_paye': float((echeancier.frais_inscription_paye or 0) + 
                                  (echeancier.tranche_1_payee or 0) + 
                                  (echeancier.tranche_2_payee or 0) + 
                                  (echeancier.tranche_3_payee or 0))
            }
            montants_info['reste_a_payer'] = montants_info['total_du'] - montants_info['total_paye']
        
        data = {
            'success': True,
            'eleve': {
                'id': eleve.id,
                'nom': eleve.nom,
                'prenom': eleve.prenom,
                'matricule': eleve.matricule,
                'classe': eleve.classe.nom,
                'ecole': eleve.classe.ecole.nom,
                'photo_url': eleve.photo.url if eleve.photo else None,
                'date_inscription': eleve.date_inscription.strftime('%d/%m/%Y') if eleve.date_inscription else None
            },
            'echeancier': montants_info,
            'has_echeancier': echeancier is not None
        }
        
        return JsonResponse(data)
        
    except Eleve.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': f'Aucun élève trouvé avec le matricule "{matricule}"'
        })
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Erreur lors de la recherche: {str(e)}'
        })

@login_required
def appliquer_remise_paiement(request, paiement_id):
    """Vue pour appliquer des remises à un paiement existant"""
    # Autorisation: admin ou droit de validation paiements (comptable)
    if not (user_is_admin(request.user) or can_validate_payments(request.user)):
        messages.error(request, "Vous n'avez pas l'autorisation pour appliquer des remises.")
        return redirect('paiements:detail_paiement', paiement_id=paiement_id)

    qs = Paiement.objects.select_related('eleve', 'type_paiement')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')
    
    paiement = get_object_or_404(qs, id=paiement_id)
    
    # Vérifier que le paiement n'est pas encore validé
    if paiement.statut == 'VALIDE':
        messages.warning(request, "Impossible d'appliquer des remises à un paiement déjà validé.")
        return redirect('paiements:detail_paiement', paiement_id=paiement.id)
    
    if request.method == 'POST':
        form = PaiementRemiseForm(request.POST, paiement=paiement)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Supprimer les anciennes remises
                    PaiementRemise.objects.filter(paiement=paiement).delete()
                    
                    # Calculer et appliquer les nouvelles remises
                    # Base de calcul = DÛ GLOBAL SCOLARITÉ (T1+T2+T3) RESTANT, hors frais d'inscription
                    # Si l'échéancier n'est pas disponible, fallback au montant du paiement
                    base_remise = paiement.montant
                    try:
                        ech = EcheancierPaiement.objects.filter(eleve=paiement.eleve, annee_scolaire=paiement.eleve.classe.annee_scolaire).first()
                        if ech:
                            t1_rest = max(Decimal('0'), (ech.tranche_1_due or 0) - (ech.tranche_1_payee or 0))
                            t2_rest = max(Decimal('0'), (ech.tranche_2_due or 0) - (ech.tranche_2_payee or 0))
                            t3_rest = max(Decimal('0'), (ech.tranche_3_due or 0) - (ech.tranche_3_payee or 0))
                            base_remise = t1_rest + t2_rest + t3_rest
                            # Sécurité: si base <= 0, on retombe sur le montant du paiement
                            if base_remise <= 0:
                                base_remise = paiement.montant
                    except Exception:
                        base_remise = paiement.montant

                    total_remise = form.calculate_total_remise(base_remise)
                    remises_details = form.get_remises_details(base_remise)
                    
                    # Créer les nouvelles associations remise-paiement
                    for detail in remises_details:
                        PaiementRemise.objects.create(
                            paiement=paiement,
                            remise=detail['remise'],
                            montant_remise=detail['montant']
                        )
                    
                    # Mettre à jour le montant du paiement (ne jamais aller sous 0)
                    from decimal import Decimal
                    # On applique la remise calculée sur la base globale au paiement courant, capped à son montant
                    montant_original = paiement.montant
                    nouveau_montant = max(Decimal('0'), montant_original - total_remise)
                    paiement.montant = nouveau_montant
                    paiement.save()
                    
                    # Messages informatifs
                    messages.success(request, f"Remises appliquées avec succès !")
                    messages.info(request, f"Montant original: {montant_original:,.0f} GNF".replace(',', ' '))
                    messages.info(request, f"Total des remises: {total_remise:,.0f} GNF".replace(',', ' '))
                    messages.info(request, f"Nouveau montant: {nouveau_montant:,.0f} GNF".replace(',', ' '))
                    
                    for detail in remises_details:
                        messages.info(request, f"• {detail['description']}")
                    
                    return redirect('paiements:detail_paiement', paiement_id=paiement.id)
                    
            except Exception as e:
                messages.error(request, f"Erreur lors de l'application des remises: {str(e)}")
    else:
        form = PaiementRemiseForm(paiement=paiement)
    
    context = {
        'form': form,
        'paiement': paiement,
        'remises_existantes': paiement.remises.all()
    }
    
    return render(request, 'paiements/appliquer_remise.html', context)

@login_required
@require_http_methods(["GET"])
def ajax_calculer_remise(request):
    """Vue AJAX pour calculer une remise en temps réel"""
    try:
        montant = Decimal(request.GET.get('montant', '0'))
        remise_id = request.GET.get('remise_id')
        
        if not montant or montant <= 0:
            return JsonResponse({'success': False, 'error': 'Montant invalide'})
        
        if not remise_id:
            return JsonResponse({'success': False, 'error': 'Remise non sélectionnée'})
        
        try:
            remise = RemiseReduction.objects.get(id=remise_id, actif=True)
        except RemiseReduction.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Remise introuvable'})
        
        # Vérifier que la remise est valide à la date actuelle
        today = date.today()
        if not (remise.date_debut <= today <= remise.date_fin):
            return JsonResponse({
                'success': False, 
                'error': f'Cette remise n\'est pas valide aujourd\'hui (valide du {remise.date_debut.strftime("%d/%m/%Y")} au {remise.date_fin.strftime("%d/%m/%Y")})'
            })
        
        # Calculer la remise
        montant_remise = remise.calculer_remise(montant)
        montant_final = montant - montant_remise
        pourcentage_remise = (montant_remise / montant * 100) if montant > 0 else 0
        
        return JsonResponse({
            'success': True,
            'calcul': {
                'montant_original': float(montant),
                'montant_remise': float(montant_remise),
                'montant_final': float(montant_final),
                'pourcentage_remise': round(pourcentage_remise, 2),
                'remise_nom': remise.nom,
                'remise_type': remise.get_type_remise_display(),
                'remise_valeur': float(remise.valeur),
                'description': f"{remise.nom} - {montant_remise:,.0f} GNF".replace(',', ' ')
            }
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({'success': False, 'error': 'Données invalides'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erreur de calcul: {str(e)}'})


@login_required
def calculateur_remise(request):
    """Vue pour le calculateur de remises (outil de simulation)"""
    form = CalculateurRemiseForm()
    resultat = None
    
    if request.method == 'POST':
        form = CalculateurRemiseForm(request.POST)
        if form.is_valid():
            resultat = form.calculate_remise_preview()
    
    # Récupérer toutes les remises actives pour affichage
    remises_actives = RemiseReduction.objects.filter(
        actif=True,
        date_debut__lte=date.today(),
        date_fin__gte=date.today()
    ).order_by('nom')
    
    context = {
        'form': form,
        'resultat': resultat,
        'remises_actives': remises_actives
    }
    
    return render(request, 'paiements/calculateur_remise.html', context)


def _calculate_payment_with_remises(paiement, remises_ids=None):
    """
    Fonction utilitaire pour calculer un paiement avec remises
    Utilisée lors de la création/modification de paiements
    """
    if not remises_ids:
        return paiement.montant, []
    
    # Base de remise: dû global de scolarité restant (T1+T2+T3), hors inscription
    # Fallback: montant du paiement si l'échéancier est indisponible
    try:
        ech = EcheancierPaiement.objects.filter(
            eleve=paiement.eleve,
            annee_scolaire=paiement.eleve.classe.annee_scolaire
        ).first()
    except Exception:
        ech = None

    if ech:
        t1_rest = max(Decimal('0'), (ech.tranche_1_due or 0) - (ech.tranche_1_payee or 0))
        t2_rest = max(Decimal('0'), (ech.tranche_2_due or 0) - (ech.tranche_2_payee or 0))
        t3_rest = max(Decimal('0'), (ech.tranche_3_due or 0) - (ech.tranche_3_payee or 0))
        base_restant = t1_rest + t2_rest + t3_rest
        montant_original = base_restant if base_restant > 0 else paiement.montant
    else:
        montant_original = paiement.montant

    total_remise = Decimal('0')
    remises_appliquees = []
    
    for remise_id in remises_ids:
        try:
            remise = RemiseReduction.objects.get(id=remise_id, actif=True)
            
            # Vérifier la validité de la remise
            today = paiement.date_paiement
            if remise.date_debut <= today <= remise.date_fin:
                # Base par défaut = base restante
                base_calcul = montant_original
                # Cas spécifique: remises à 3% doivent s'appliquer sur le montant annuel par cycle
                try:
                    if remise.type_remise == 'POURCENTAGE' and Decimal(remise.valeur) == Decimal('3'):
                        annuel = _tuition_annual_by_cycle(paiement.eleve)
                        if annuel and annuel > 0:
                            # arrondi au millier avant calcul pour propreté
                            from math import floor
                            annuel_arrondi = (annuel // Decimal('1000')) * Decimal('1000')
                            base_calcul = annuel_arrondi
                except Exception:
                    pass

                montant_remise = remise.calculer_remise(base_calcul)
                total_remise += montant_remise
                remises_appliquees.append({
                    'remise': remise,
                    'montant': montant_remise
                })
        except RemiseReduction.DoesNotExist:
            continue
    
    # Le montant final ne peut pas être négatif
    montant_final = max(Decimal('0'), paiement.montant - total_remise)
    
    return montant_final, remises_appliquees


@can_view_reports
def rapport_remises(request):
    """Rapport: élèves ayant des remises appliquées avec total des remises.
    Filtres optionnels: date_debut, date_fin (sur date_paiement)"""
    # Récup filtres
    date_debut_str = request.GET.get('date_debut')
    date_fin_str = request.GET.get('date_fin')
    date_debut = None
    date_fin = None
    try:
        if date_debut_str:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
        if date_fin_str:
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
    except Exception:
        date_debut = None
        date_fin = None

    qs = PaiementRemise.objects.select_related(
        'paiement', 'paiement__eleve', 'paiement__eleve__classe', 'paiement__eleve__classe__ecole'
    ).filter(
        paiement__statut='VALIDE'
    )

    # Scope école
    try:
        ecole = user_school(request.user)
        if ecole:
            qs = qs.filter(paiement__eleve__classe__ecole=ecole)
    except Exception:
        pass

    if date_debut:
        qs = qs.filter(paiement__date_paiement__gte=date_debut)
    if date_fin:
        qs = qs.filter(paiement__date_paiement__lte=date_fin)

    # Filtre texte unique (q) : nom/prénom élève, matricule, classe
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(paiement__eleve__prenom__icontains=q) |
            Q(paiement__eleve__nom__icontains=q) |
            Q(paiement__eleve__matricule__icontains=q) |
            Q(paiement__eleve__classe__nom__icontains=q)
        )

    # Agrégations par élève
    aggs = (
        qs.values(
            'paiement__eleve',
            'paiement__eleve__prenom',
            'paiement__eleve__nom',
            'paiement__eleve__matricule',
            'paiement__eleve__classe__nom',
        )
        .annotate(total_remise=Sum('montant_remise'), nb_remises=Count('id'))
    )

    # Pas de filtres supplémentaires sur agrégats pour le mode "recherche unique"

    aggs = aggs.order_by('-total_remise')

    total_global = qs.aggregate(total=Sum('montant_remise'))['total'] or Decimal('0')

    context = {
        'rows': aggs,
        'total_global': total_global,
        'date_debut': date_debut_str or '',
        'date_fin': date_fin_str or '',
        'titre_page': 'Rapport des remises appliquées',
        # Préserver valeur du champ de recherche unique
        'q': q,
    }

    return render(request, 'paiements/rapport_remises.html', context)
