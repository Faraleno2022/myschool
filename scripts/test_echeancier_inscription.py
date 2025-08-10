#!/usr/bin/env python
"""
Script de test pour créer un échéancier avec les nouveaux frais d'inscription
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve, GrilleTarifaire
from paiements.models import EcheancierPaiement, TypePaiement
from decimal import Decimal

def test_echeancier_inscription():
    """Teste la création d'un échéancier avec les frais d'inscription"""
    
    print("🎓 Test de création d'échéancier avec frais d'inscription...")
    print("=" * 60)
    
    # Récupérer un élève de test de chaque école
    eleves_test = []
    
    # Élève de Somayah
    eleve_somayah = Eleve.objects.filter(
        classe__ecole__nom__icontains='somayah'
    ).first()
    
    # Élève de Sonfonia
    eleve_sonfonia = Eleve.objects.filter(
        classe__ecole__nom__icontains='sonfonia'
    ).first()
    
    if eleve_somayah:
        eleves_test.append(eleve_somayah)
    if eleve_sonfonia:
        eleves_test.append(eleve_sonfonia)
    
    if not eleves_test:
        print("❌ Aucun élève trouvé pour le test")
        return
    
    # Tester pour chaque élève
    for eleve in eleves_test:
        print(f"\n🧑‍🎓 Test pour {eleve.nom_complet}")
        print(f"   École: {eleve.classe.ecole.nom}")
        print(f"   Classe: {eleve.classe}")
        
        # Récupérer la grille tarifaire
        grille = GrilleTarifaire.objects.filter(
            ecole=eleve.classe.ecole,
            niveau=eleve.classe.niveau,
            annee_scolaire='2024-2025'
        ).first()
        
        if not grille:
            print("   ❌ Aucune grille tarifaire trouvée")
            continue
        
        print(f"   💰 Frais d'inscription: {grille.frais_inscription:,.0f} GNF")
        print(f"   📚 Scolarité totale: {grille.total_scolarite:,.0f} GNF")
        
        # Vérifier si un échéancier existe déjà
        echeancier_existant = EcheancierPaiement.objects.filter(
            eleve=eleve,
            annee_scolaire='2024-2025'
        ).first()
        
        if echeancier_existant:
            print("   ℹ️  Échéancier existant trouvé")
            echeancier = echeancier_existant
        else:
            # Créer un nouvel échéancier
            print("   ✨ Création d'un nouvel échéancier...")
            
            today = datetime.now().date()
            echeancier = EcheancierPaiement.objects.create(
                eleve=eleve,
                annee_scolaire='2024-2025',
                
                # Frais d'inscription
                frais_inscription_du=grille.frais_inscription,
                date_echeance_inscription=today + timedelta(days=30),
                
                # Tranches de scolarité
                tranche_1_due=grille.tranche_1,
                date_echeance_tranche_1=today + timedelta(days=60),
                
                tranche_2_due=grille.tranche_2,
                date_echeance_tranche_2=today + timedelta(days=120),
                
                tranche_3_due=grille.tranche_3,
                date_echeance_tranche_3=today + timedelta(days=180),
            )
            print("   ✅ Échéancier créé avec succès!")
        
        # Afficher le détail de l'échéancier
        print(f"\n   📋 Détail de l'échéancier:")
        print(f"      🎓 Frais d'inscription: {echeancier.frais_inscription_du:,.0f} GNF (échéance: {echeancier.date_echeance_inscription})")
        print(f"      📚 1ère tranche: {echeancier.tranche_1_due:,.0f} GNF (échéance: {echeancier.date_echeance_tranche_1})")
        print(f"      📚 2ème tranche: {echeancier.tranche_2_due:,.0f} GNF (échéance: {echeancier.date_echeance_tranche_2})")
        print(f"      📚 3ème tranche: {echeancier.tranche_3_due:,.0f} GNF (échéance: {echeancier.date_echeance_tranche_3})")
        print(f"      💰 Total dû: {echeancier.total_du:,.0f} GNF")
        print(f"      💳 Total payé: {echeancier.total_paye:,.0f} GNF")
        print(f"      🔴 Solde restant: {echeancier.solde_restant:,.0f} GNF")
        print(f"      📊 Pourcentage payé: {echeancier.pourcentage_paye:.1f}%")
        print(f"      📈 Statut: {echeancier.get_statut_display()}")
    
    print(f"\n✅ Test terminé avec succès!")
    print(f"📊 {len(eleves_test)} échéancier(s) testé(s)")

if __name__ == '__main__':
    test_echeancier_inscription()
