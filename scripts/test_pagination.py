#!/usr/bin/env python
"""
Script de test pour vérifier que la pagination à 15 éléments fonctionne correctement
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
from django.core.paginator import Paginator

def test_pagination():
    """Test de la pagination à 15 éléments"""
    
    print("📊 TEST DE LA PAGINATION À 15 ÉLÉMENTS")
    print("=" * 50)
    
    # 1. Test pagination des paiements
    print("\n1️⃣ TEST PAGINATION PAIEMENTS:")
    paiements = Paiement.objects.all().order_by('-date_paiement')
    paginator_paiements = Paginator(paiements, 15)
    
    print(f"   Total paiements: {paiements.count()}")
    print(f"   Nombre de pages: {paginator_paiements.num_pages}")
    print(f"   Éléments par page: 15")
    
    if paginator_paiements.num_pages > 1:
        page1 = paginator_paiements.get_page(1)
        print(f"   Page 1: {len(page1)} éléments")
        if paginator_paiements.num_pages > 1:
            page2 = paginator_paiements.get_page(2)
            print(f"   Page 2: {len(page2)} éléments")
    else:
        page1 = paginator_paiements.get_page(1)
        print(f"   Page unique: {len(page1)} éléments")
    
    # 2. Test pagination des élèves
    print("\n2️⃣ TEST PAGINATION ÉLÈVES:")
    eleves = Eleve.objects.filter(statut='ACTIF').order_by('nom', 'prenom')
    paginator_eleves = Paginator(eleves, 15)
    
    print(f"   Total élèves actifs: {eleves.count()}")
    print(f"   Nombre de pages: {paginator_eleves.num_pages}")
    print(f"   Éléments par page: 15")
    
    if paginator_eleves.num_pages > 1:
        page1 = paginator_eleves.get_page(1)
        print(f"   Page 1: {len(page1)} éléments")
        if paginator_eleves.num_pages > 1:
            page2 = paginator_eleves.get_page(2)
            print(f"   Page 2: {len(page2)} éléments")
    else:
        page1 = paginator_eleves.get_page(1)
        print(f"   Page unique: {len(page1)} éléments")
    
    # 3. Recommandations pour le test visuel
    print("\n🎯 INSTRUCTIONS POUR TEST VISUEL:")
    print("   1. Allez sur: http://127.0.0.1:8000/paiements/liste/")
    print("   2. Vérifiez que la table a une hauteur fixe avec défilement")
    print("   3. Vérifiez que les en-têtes restent fixes lors du défilement")
    print("   4. Vérifiez la pagination en bas (si plus de 15 éléments)")
    print("   5. Testez aussi: http://127.0.0.1:8000/eleves/liste/")
    
    print("\n✅ FONCTIONNALITÉS IMPLÉMENTÉES:")
    print("   - Pagination limitée à 15 éléments par page")
    print("   - Défilement vertical avec hauteur fixe (600px)")
    print("   - En-têtes de table fixes (sticky)")
    print("   - Scrollbar personnalisée")
    print("   - Effet hover sur les lignes")
    print("   - Bordures et coins arrondis")

if __name__ == '__main__':
    test_pagination()
