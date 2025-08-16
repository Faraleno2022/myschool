from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.db import transaction, IntegrityError
from django.utils import timezone
from decimal import Decimal
from datetime import date, datetime
import os

from .models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise
from eleves.models import Eleve, GrilleTarifaire, Classe
from .forms import PaiementForm, EcheancierForm, RechercheForm
from .remise_forms import PaiementRemiseForm, CalculateurRemiseForm
from utilisateurs.utils import user_is_admin, filter_by_user_school, user_school
from utilisateurs.permissions import can_add_payments, can_modify_payments, can_delete_payments, can_validate_payments
from rapports.utils import _draw_header_and_watermark
from django.views.decorators.http import require_http_methods
import re
import unicodedata

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
        restant <= (FRAIS_INSCRIPTION + t1_restant + Decimal('50000'))):  # Tolérance
        
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
    elif (inscription_restant == 0 and restant >= scolarite_restante * Decimal('0.9') and 
          restant <= scolarite_restante * Decimal('1.1')):  # Tolérance de ±10%
        
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
            # Si un type est ciblé, utiliser la validation centralisée
            erreur = valider_surpaiement(cible, restant)
            if erreur:
                warnings.append(erreur)
                return {'warnings': warnings, 'info': infos}
            
            # Paiement ciblé validé
            due_field, paid_field, due_date_field, label = tranche_data(cible)
            paid = getattr(echeancier, paid_field)
            setattr(echeancier, paid_field, paid + restant)
            restant = Decimal('0')
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

    return {'warnings': warnings, 'info': infos}


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
        
        # Répartir le reste proportionnellement entre les tranches
        if montant_restant > 0:
            total_tranches_restantes = tranche_1_restante + tranche_2_restante + tranche_3_restante
            
            if total_tranches_restantes > 0:
                # Répartition proportionnelle
                if tranche_1_restante > 0:
                    proportion_1 = tranche_1_restante / total_tranches_restantes
                    montant_tranche_1 = min(tranche_1_restante, montant_restant * proportion_1)
                    allocations['tranche_1'] = montant_tranche_1
                    montant_restant -= montant_tranche_1
                    infos.append(f"✓ 1ère tranche: {int(montant_tranche_1):,} GNF".replace(',', ' '))
                
                if tranche_2_restante > 0 and montant_restant > 0:
                    proportion_2 = tranche_2_restante / total_tranches_restantes
                    montant_tranche_2 = min(tranche_2_restante, montant_restant * proportion_2)
                    allocations['tranche_2'] = montant_tranche_2
                    montant_restant -= montant_tranche_2
                    infos.append(f"✓ 2ème tranche: {int(montant_tranche_2):,} GNF".replace(',', ' '))
                
                if tranche_3_restante > 0 and montant_restant > 0:
                    # Le reste va à la 3ème tranche
                    montant_tranche_3 = min(tranche_3_restante, montant_restant)
                    allocations['tranche_3'] = montant_tranche_3
                    montant_restant -= montant_tranche_3
                    infos.append(f"✓ 3ème tranche: {int(montant_tranche_3):,} GNF".replace(',', ' '))
    
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
            # Type non combiné: déléguer à la logique existante
            return _allocate_payment_to_echeancier(paiement, echeancier)
    
    # Appliquer les allocations à l'échéancier
    if allocations['inscription'] > 0:
        echeancier.frais_inscription_paye = (echeancier.frais_inscription_paye or Decimal('0')) + allocations['inscription']
    
    if allocations['tranche_1'] > 0:
        echeancier.tranche_1_payee = (echeancier.tranche_1_payee or Decimal('0')) + allocations['tranche_1']
    
    if allocations['tranche_2'] > 0:
        echeancier.tranche_2_payee = (echeancier.tranche_2_payee or Decimal('0')) + allocations['tranche_2']
    
    if allocations['tranche_3'] > 0:
        echeancier.tranche_3_payee = (echeancier.tranche_3_payee or Decimal('0')) + allocations['tranche_3']
    
    # Vérifier s'il reste un montant non alloué
    if montant_restant > 0:
        warnings.append(f"⚠️ Montant non alloué: {int(montant_restant):,} GNF - Vérifiez les montants dus".replace(',', ' '))
    
    # Calculer le nouveau solde
    total_du = (echeancier.frais_inscription_du or Decimal('0')) + (echeancier.tranche_1_due or Decimal('0')) + (echeancier.tranche_2_due or Decimal('0')) + (echeancier.tranche_3_due or Decimal('0'))
    total_paye = (echeancier.frais_inscription_paye or Decimal('0')) + (echeancier.tranche_1_payee or Decimal('0')) + (echeancier.tranche_2_payee or Decimal('0')) + (echeancier.tranche_3_payee or Decimal('0'))
    nouveau_solde = total_du - total_paye
    
    # Mettre à jour le statut
    if nouveau_solde <= 0:
        echeancier.statut = 'PAYE_COMPLET'
        infos.append("🎉 Échéancier entièrement réglé ! Félicitations.")
    else:
        # Vérifier les retards
        now = timezone.now().date()
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
    
    # Calculer le solde restant = total_du - total_paye
    echeanciers_avec_solde = echeanciers_qs.annotate(
        total_du=F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due'),
        total_paye=F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'),
        solde_calcule=F('total_du') - F('total_paye')
    )
    
    # Élèves en retard (solde > 0)
    eleves_retard = echeanciers_avec_solde.filter(
        solde_calcule__gt=0
    ).count()
    
    # Si pas d'échéanciers avec solde > 0, utiliser le statut EN_RETARD
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
        
        # Calculer le solde restant = total_du - total_paye
        echeanciers_avec_solde = echeanciers_qs.annotate(
            total_du=F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due'),
            total_paye=F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'),
            solde_calcule=F('total_du') - F('total_paye')
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
@can_add_payments
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
            paiement.statut = 'VALIDE'
            paiement.valide_par = request.user
            paiement.date_validation = timezone.now()
            paiement.save()
            
            # Impacter l'échéancier à la validation avec allocation intelligente
            try:
                echeancier = paiement.eleve.echeancier
                
                # Utiliser la nouvelle fonction d'allocation intelligente pour les paiements combinés
                feedback = _allocate_combined_payment(paiement, echeancier)
                
                # Afficher les messages de feedback
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
    c.saveState()
    try:
        # Chemin vers le logo
        logo_path = None
        try:
            logo_path = finders.find('logos/logo.png')
        except Exception:
            pass
        # Fallback: chemin absolu vers static/logos/logo.png si non trouvé par les finders
        if not logo_path:
            try:
                from django.conf import settings
                candidate = os.path.join(getattr(settings, 'BASE_DIR', ''), 'static', 'logos', 'logo.png')
                if candidate and os.path.exists(candidate):
                    logo_path = candidate
            except Exception:
                pass
        
        if logo_path:
            # Taille ~150% de la largeur de page (comme dans fiche d'inscription)
            wm_width = width * 1.5
            wm_height = wm_width  # carré approximatif, preserveAspectRatio activera le ratio réel
            wm_x = (width - wm_width) / 2
            wm_y = (height - wm_height) / 2
            
            # Opacité faible
            try:
                c.setFillAlpha(0.08)
            except Exception:
                pass
            
            # Légère rotation pour l'effet filigrane
            c.translate(width / 2.0, height / 2.0)
            c.rotate(30)
            c.translate(-width / 2.0, -height / 2.0)
            
            c.drawImage(logo_path, wm_x, wm_y, width=wm_width, height=wm_height, preserveAspectRatio=True, mask='auto')
    finally:
        c.restoreState()

    # En-tête avec logo + titre (ajusté pour éviter chevauchement avec photo élève)
    c.saveState()
    try:
        if logo_path:
            c.drawImage(logo_path, margin_x, height - margin_y - 30, width=60, height=30, preserveAspectRatio=True, mask='auto')
        c.setFillColor(colors.HexColor('#0056b3'))
        try:
            c.setFont("MainFont-Bold", 20)
        except:
            c.setFont("Helvetica-Bold", 20)
        
        # Centrer le nom de l'école
        text = "École Moderne HADJA KANFING DIANÉ"
        text_width = c.stringWidth(text, "MainFont-Bold", 20) if "MainFont-Bold" in c.getAvailableFonts() else c.stringWidth(text, "Helvetica-Bold", 20)
        c.drawString((width - text_width) / 2, height - margin_y - 10, text)
        
        c.setFillColor(colors.black)
        try:
            c.setFont("MainFont-Bold", 16)
        except:
            c.setFont("Helvetica-Bold", 16)
        
        # Centrer le titre du reçu
        text = f"REÇU DE PAIEMENT N° {paiement.numero_recu}"
        text_width = c.stringWidth(text, "MainFont-Bold", 16) if "MainFont-Bold" in c.getAvailableFonts() else c.stringWidth(text, "Helvetica-Bold", 16)
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
        c.setFont("MainFont", 13)
    except:
        c.setFont("Helvetica", 13)

    def line(label, value):
        nonlocal y
        try:
            c.setFont("MainFont-Bold", 13)
        except:
            c.setFont("Helvetica-Bold", 13)
        c.drawString(margin_x, y, f"{label} :")
        try:
            c.setFont("MainFont", 13)
        except:
            c.setFont("Helvetica", 13)
        c.drawString(margin_x + 140, y, str(value))
        y -= 18

    # Formatage
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
    line("Montant", f"{montant_fmt} GNF")
    line("Statut", paiement.get_statut_display())
    if paiement.reference_externe:
        line("Référence", paiement.reference_externe)

    # Observations
    if paiement.observations:
        y -= 6
        try:
            c.setFont("MainFont-Bold", 13)
        except:
            c.setFont("Helvetica-Bold", 13)
        c.drawString(margin_x, y, "Observations :")
        y -= 16
        try:
            c.setFont("MainFont", 12)
        except:
            c.setFont("Helvetica", 12)
        text_obj = c.beginText(margin_x, y)
        text_obj.setLeading(16)
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

        def fmt_money(d):
            return f"{int(d):,}".replace(',', ' ') + " GNF"

        y -= 10
        try:
            c.setFont("MainFont-Bold", 14)
        except:
            c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_x, y, "Résumé de l'échéancier")
        y -= 20
        try:
            c.setFont("MainFont", 13)
        except:
            c.setFont("Helvetica", 13)
        line("Total à payer", fmt_money(total_a_payer))
        line("Déjà payé", fmt_money(total_paye))
        line("Reste à payer", fmt_money(reste))

        # Détail par tranche
        y -= 4
        try:
            c.setFont("MainFont-Bold", 13)
        except:
            c.setFont("Helvetica-Bold", 13)
        c.drawString(margin_x, y, "Détail des tranches :")
        y -= 18
        try:
            c.setFont("Arial", 12)
        except:
            c.setFont("Helvetica", 12)
        detail = [
            ("Inscription", echeancier.frais_inscription_du or Decimal('0'), paye_insc),
            ("Tranche 1", echeancier.tranche_1_due or Decimal('0'), paye_t1),
            ("Tranche 2", echeancier.tranche_2_due or Decimal('0'), paye_t2),
            ("Tranche 3", echeancier.tranche_3_due or Decimal('0'), paye_t3),
        ]
        for label, due, paid in detail:
            rest = max(Decimal('0'), due - paid)
            c.drawString(margin_x, y, f"{label} : dû {fmt_money(due)} | payé {fmt_money(paid)} | reste {fmt_money(rest)}")
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
                    montant_original = paiement.montant
                    total_remise = form.calculate_total_remise(montant_original)
                    remises_details = form.get_remises_details(montant_original)
                    
                    # Créer les nouvelles associations remise-paiement
                    for detail in remises_details:
                        PaiementRemise.objects.create(
                            paiement=paiement,
                            remise=detail['remise'],
                            montant_remise=detail['montant']
                        )
                    
                    # Mettre à jour le montant du paiement
                    nouveau_montant = montant_original - total_remise
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
    
    montant_original = paiement.montant
    total_remise = Decimal('0')
    remises_appliquees = []
    
    for remise_id in remises_ids:
        try:
            remise = RemiseReduction.objects.get(id=remise_id, actif=True)
            
            # Vérifier la validité de la remise
            today = paiement.date_paiement
            if remise.date_debut <= today <= remise.date_fin:
                montant_remise = remise.calculer_remise(montant_original)
                total_remise += montant_remise
                remises_appliquees.append({
                    'remise': remise,
                    'montant': montant_remise
                })
        except RemiseReduction.DoesNotExist:
            continue
    
    # Le montant final ne peut pas être négatif
    montant_final = max(Decimal('0'), montant_original - total_remise)
    
    return montant_final, remises_appliquees
