#!/usr/bin/env python
"""
Script pour vérifier les calculs des paiements REC20250001 et REC20250002
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import Paiement
from eleves.models import Eleve

def main():
    # Chercher les paiements spécifiques
    print("=== RECHERCHE DES PAIEMENTS ===")
    paiements = Paiement.objects.filter(numero_recu__in=['REC20250001', 'REC20250002']).order_by('date_paiement')
    
    if not paiements.exists():
        print("Aucun paiement trouvé avec les numéros REC20250001 ou REC20250002")
        return
    
    # Identifier l'élève concerné
    eleve = paiements.first().eleve
    print(f'Élève: {eleve.nom} {eleve.prenom}')
    print(f'Matricule: {eleve.matricule}')
    print(f'Classe: {eleve.classe}')
    
    # Récupérer l'échéancier
    echeancier = eleve.echeancier
    print(f'\n=== ÉCHÉANCIER INITIAL ===')
    print(f'Frais inscription: {echeancier.frais_inscription:,} GNF'.replace(',', ' '))
    print(f'Tranche 1: {echeancier.tranche_1:,} GNF'.replace(',', ' '))
    print(f'Tranche 2: {echeancier.tranche_2:,} GNF'.replace(',', ' '))
    print(f'Tranche 3: {echeancier.tranche_3:,} GNF'.replace(',', ' '))
    print(f'Total: {echeancier.total_a_payer:,} GNF'.replace(',', ' '))

    print(f'\n=== MONTANTS PAYÉS ACTUELS ===')
    print(f'Inscription payée: {echeancier.frais_inscription_paye or 0:,} GNF'.replace(',', ' '))
    print(f'Tranche 1 payée: {echeancier.tranche_1_payee or 0:,} GNF'.replace(',', ' '))
    print(f'Tranche 2 payée: {echeancier.tranche_2_payee or 0:,} GNF'.replace(',', ' '))
    print(f'Tranche 3 payée: {echeancier.tranche_3_payee or 0:,} GNF'.replace(',', ' '))

    print(f'\n=== SOLDES RESTANTS ===')
    inscription_restante = (echeancier.frais_inscription or 0) - (echeancier.frais_inscription_paye or 0)
    tranche1_restante = (echeancier.tranche_1 or 0) - (echeancier.tranche_1_payee or 0)
    tranche2_restante = (echeancier.tranche_2 or 0) - (echeancier.tranche_2_payee or 0)
    tranche3_restante = (echeancier.tranche_3 or 0) - (echeancier.tranche_3_payee or 0)
    
    print(f'Inscription restante: {inscription_restante:,} GNF'.replace(',', ' '))
    print(f'Tranche 1 restante: {tranche1_restante:,} GNF'.replace(',', ' '))
    print(f'Tranche 2 restante: {tranche2_restante:,} GNF'.replace(',', ' '))
    print(f'Tranche 3 restante: {tranche3_restante:,} GNF'.replace(',', ' '))
    print(f'Solde total restant: {echeancier.solde_restant:,} GNF'.replace(',', ' '))

    # Afficher tous les paiements de l'élève
    tous_paiements = Paiement.objects.filter(eleve=eleve).order_by('date_paiement')
    print(f'\n=== HISTORIQUE COMPLET DES PAIEMENTS ===')
    total_paye = 0
    for p in tous_paiements:
        print(f'{p.numero_recu}: {p.montant:,} GNF - {p.type_paiement.nom} - {p.statut} - {p.date_paiement}'.replace(',', ' '))
        if p.statut == 'VALIDE':
            total_paye += p.montant
    
    print(f'\n=== ANALYSE DES CALCULS ===')
    print(f'Total payé (somme des paiements validés): {total_paye:,} GNF'.replace(',', ' '))
    total_alloue = (echeancier.frais_inscription_paye or 0) + (echeancier.tranche_1_payee or 0) + (echeancier.tranche_2_payee or 0) + (echeancier.tranche_3_payee or 0)
    print(f'Total alloué dans échéancier: {total_alloue:,} GNF'.replace(',', ' '))
    
    if total_paye != total_alloue:
        print(f'⚠️  PROBLÈME DÉTECTÉ: Différence de {total_paye - total_alloue:,} GNF'.replace(',', ' '))
    else:
        print('✅ Cohérence entre paiements et allocations')
        
    # Analyse détaillée des paiements spécifiques
    print(f'\n=== ANALYSE DÉTAILLÉE DES PAIEMENTS CONCERNÉS ===')
    for p in paiements:
        print(f'\n--- Paiement {p.numero_recu} ---')
        print(f'Type: {p.type_paiement.nom}')
        print(f'Montant: {p.montant:,} GNF'.replace(',', ' '))
        print(f'Date: {p.date_paiement}')
        print(f'Statut: {p.statut}')
        
        # Analyse selon le type de paiement
        if 'inscription' in p.type_paiement.nom.lower() and 'tranche' in p.type_paiement.nom.lower():
            print(f'🔍 Paiement combiné détecté')
            if '1' in p.type_paiement.nom:
                inscription_attendue = 30000
                tranche1_attendue = p.montant - inscription_attendue
                print(f'Répartition attendue:')
                print(f'  - Inscription: {inscription_attendue:,} GNF'.replace(',', ' '))
                print(f'  - Tranche 1: {tranche1_attendue:,} GNF'.replace(',', ' '))
        elif 'tranche 2' in p.type_paiement.nom.lower():
            print(f'🔍 Paiement de tranche 2 uniquement')
            print(f'Montant attendu en tranche 2: {p.montant:,} GNF'.replace(',', ' '))
    
    # Vérification de cohérence spécifique
    print(f'\n=== VÉRIFICATION DE COHÉRENCE ===')
    
    # Calculer ce qui devrait être payé selon les paiements
    paiement_1 = paiements.filter(numero_recu='REC20250001').first()
    paiement_2 = paiements.filter(numero_recu='REC20250002').first()
    
    if paiement_1 and paiement_2:
        print(f'REC20250001: {paiement_1.montant:,} GNF ({paiement_1.type_paiement.nom})'.replace(',', ' '))
        print(f'REC20250002: {paiement_2.montant:,} GNF ({paiement_2.type_paiement.nom})'.replace(',', ' '))
        
        # Calcul théorique selon les types
        if 'inscription' in paiement_1.type_paiement.nom.lower() and 'tranche 1' in paiement_1.type_paiement.nom.lower():
            inscription_theorique = 30000
            tranche1_theorique = paiement_1.montant - 30000
            tranche2_theorique = paiement_2.montant
            
            print(f'\nRépartition théorique attendue:')
            print(f'  Inscription: {inscription_theorique:,} GNF'.replace(',', ' '))
            print(f'  Tranche 1: {tranche1_theorique:,} GNF'.replace(',', ' '))
            print(f'  Tranche 2: {tranche2_theorique:,} GNF'.replace(',', ' '))
            print(f'  Total: {inscription_theorique + tranche1_theorique + tranche2_theorique:,} GNF'.replace(',', ' '))
            
            # Comparer avec l'échéancier actuel
            print(f'\nComparaison avec échéancier:')
            print(f'  Inscription payée: {echeancier.frais_inscription_paye or 0:,} GNF (attendu: {inscription_theorique:,})'.replace(',', ' '))
            print(f'  Tranche 1 payée: {echeancier.tranche_1_payee or 0:,} GNF (attendu: {tranche1_theorique:,})'.replace(',', ' '))
            print(f'  Tranche 2 payée: {echeancier.tranche_2_payee or 0:,} GNF (attendu: {tranche2_theorique:,})'.replace(',', ' '))

if __name__ == '__main__':
    main()
