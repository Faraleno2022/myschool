#!/usr/bin/env python
"""
Script de test pour vérifier l'amélioration de la lisibilité du tableau des paiements
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import Paiement
from eleves.models import Eleve

def test_table_readability():
    """Test de la lisibilité améliorée du tableau des paiements"""
    
    print("📋 TEST DE LA LISIBILITÉ DU TABLEAU DES PAIEMENTS")
    print("=" * 60)
    
    # 1. Vérifier les données disponibles
    print("\n1️⃣ DONNÉES DISPONIBLES:")
    paiements = Paiement.objects.all()[:5]  # Prendre 5 paiements pour le test
    
    print(f"   Nombre total de paiements: {Paiement.objects.count()}")
    print(f"   Paiements pour le test: {len(paiements)}")
    
    # 2. Afficher les informations qui seront mieux formatées
    print("\n2️⃣ INFORMATIONS AMÉLIORÉES DANS LE TABLEAU:")
    
    for i, paiement in enumerate(paiements, 1):
        print(f"\n   Paiement {i}: {paiement.numero_recu}")
        print(f"   ├─ Élève: {paiement.eleve.prenom} {paiement.eleve.nom}")
        print(f"   ├─ Matricule: {paiement.eleve.matricule}")
        print(f"   ├─ Classe: {paiement.eleve.classe.nom}")
        print(f"   ├─ École: {paiement.eleve.classe.ecole.nom}")
        print(f"   ├─ Type: {paiement.type_paiement.nom}")
        print(f"   ├─ Montant: {paiement.montant:,} GNF".replace(',', ' '))
        print(f"   ├─ Mode: {paiement.mode_paiement.nom}")
        if hasattr(paiement.mode_paiement, 'frais_supplementaires') and paiement.mode_paiement.frais_supplementaires:
            print(f"   ├─ Frais supp: {paiement.mode_paiement.frais_supplementaires:,} GNF".replace(',', ' '))
        print(f"   ├─ Statut: {paiement.get_statut_display()}")
        print(f"   ├─ Date paiement: {paiement.date_paiement.strftime('%d/%m/%Y')}")
        print(f"   ├─ Date création: {paiement.date_creation.strftime('%d/%m/%Y à %H:%M')}")
        if paiement.valide_par:
            print(f"   ├─ Validé par: {paiement.valide_par.username}")
        if paiement.date_validation:
            print(f"   └─ Date validation: {paiement.date_validation.strftime('%d/%m/%Y à %H:%M')}")
        else:
            print(f"   └─ Non validé")
    
    # 3. Améliorations apportées
    print("\n3️⃣ AMÉLIORATIONS APPORTÉES AU TABLEAU:")
    print("   ✅ Informations élève sur plusieurs lignes:")
    print("      - Nom/Prénom sur la première ligne")
    print("      - Matricule sur une ligne séparée")
    print("      - Classe et École sur une ligne séparée")
    
    print("\n   ✅ Montants avec mise en forme:")
    print("      - Montant principal en gras")
    print("      - Frais supplémentaires sur ligne séparée (si applicable)")
    print("      - Séparateurs de milliers avec espaces")
    
    print("\n   ✅ Statut avec informations contextuelles:")
    print("      - Statut principal avec icône")
    print("      - Validé par qui (si validé)")
    print("      - Date de création (si en attente)")
    
    print("\n   ✅ Dates et heures séparées:")
    print("      - Date de paiement en gras")
    print("      - Heure de création en petite taille")
    
    print("\n   ✅ Mode de paiement avec détails:")
    print("      - Badge coloré pour le mode")
    print("      - Référence transaction (si applicable)")
    
    # 4. Instructions pour le test visuel
    print("\n🎯 INSTRUCTIONS POUR TEST VISUEL:")
    print("   1. Allez sur: http://127.0.0.1:8000/paiements/liste/")
    print("   2. Vérifiez que chaque ligne du tableau est bien aérée")
    print("   3. Vérifiez les retours à la ligne dans chaque colonne:")
    print("      - Colonne Élève: Nom, puis matricule, puis classe/école")
    print("      - Colonne Montant: Montant principal + frais (si applicable)")
    print("      - Colonne Statut: Statut + info contextuelle")
    print("      - Colonne Date: Date + heure")
    print("   4. Testez avec différents filtres pour voir tous les cas")
    
    print("\n📊 STATISTIQUES DES AMÉLIORATIONS:")
    statuts = {}
    modes = {}
    for paiement in Paiement.objects.all():
        statuts[paiement.statut] = statuts.get(paiement.statut, 0) + 1
        modes[paiement.mode_paiement.nom] = modes.get(paiement.mode_paiement.nom, 0) + 1
    
    print(f"   Répartition par statut:")
    for statut, count in statuts.items():
        print(f"     - {statut}: {count} paiement(s)")
    
    print(f"   Répartition par mode:")
    for mode, count in modes.items():
        print(f"     - {mode}: {count} paiement(s)")
    
    print("\n✅ LISIBILITÉ AMÉLIORÉE:")
    print("   - Informations mieux organisées visuellement")
    print("   - Retours à la ligne appropriés")
    print("   - Hiérarchie visuelle claire")
    print("   - Informations contextuelles ajoutées")
    print("   - Tableau plus aéré et professionnel")

if __name__ == '__main__':
    test_table_readability()
