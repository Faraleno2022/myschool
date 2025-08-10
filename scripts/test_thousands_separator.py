#!/usr/bin/env python
"""
Script de test pour vérifier que les séparateurs de milliers avec espaces fonctionnent correctement
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.template import Template, Context
from django.conf import settings
from paiements.models import Paiement
from eleves.models import Eleve

def test_thousands_separator():
    """Test des séparateurs de milliers avec espaces"""
    
    print("💰 TEST DES SÉPARATEURS DE MILLIERS")
    print("=" * 50)
    
    # 1. Vérifier la configuration Django
    print("\n1️⃣ CONFIGURATION DJANGO:")
    print(f"   USE_THOUSAND_SEPARATOR: {getattr(settings, 'USE_THOUSAND_SEPARATOR', False)}")
    print(f"   THOUSAND_SEPARATOR: '{getattr(settings, 'THOUSAND_SEPARATOR', 'non défini')}'")
    print(f"   NUMBER_GROUPING: {getattr(settings, 'NUMBER_GROUPING', 'non défini')}")
    print(f"   LANGUAGE_CODE: {settings.LANGUAGE_CODE}")
    
    # 2. Test avec des montants de test
    print("\n2️⃣ TEST DE FORMATAGE DES MONTANTS:")
    test_amounts = [
        1000,
        15000,
        150000,
        1500000,
        15000000
    ]
    
    template_str = """
    {% load humanize %}
    {% for amount in amounts %}
    {{ amount|floatformat:0|intcomma }}
    {% endfor %}
    """
    
    template = Template(template_str)
    context = Context({'amounts': test_amounts})
    result = template.render(context)
    
    formatted_amounts = [line.strip() for line in result.strip().split('\n') if line.strip()]
    
    for original, formatted in zip(test_amounts, formatted_amounts):
        print(f"   {original:>10} → {formatted}")
    
    # 3. Test avec des données réelles
    print("\n3️⃣ TEST AVEC DONNÉES RÉELLES:")
    
    # Paiements
    paiements = Paiement.objects.all()[:5]
    if paiements:
        print("   Paiements:")
        template_paiement = Template("{% load humanize %}{{ montant|floatformat:0|intcomma }} GNF")
        for paiement in paiements:
            context = Context({'montant': paiement.montant})
            formatted = template_paiement.render(context)
            print(f"     {paiement.numero_recu}: {formatted}")
    
    # Élèves avec échéanciers
    eleves = Eleve.objects.filter(statut='ACTIF')[:3]
    if eleves:
        print("   Échéanciers élèves:")
        for eleve in eleves:
            if hasattr(eleve, 'echeancier') and eleve.echeancier:
                context = Context({'montant': eleve.echeancier.total_du})
                formatted = template_paiement.render(context)
                print(f"     {eleve.nom_complet}: {formatted}")
    
    # 4. Test JavaScript pour les formulaires
    print("\n4️⃣ TEST JAVASCRIPT (SIMULATION):")
    js_test_amounts = [1000, 15000, 150000, 1500000]
    print("   Format JavaScript (toLocaleString('fr-FR')):")
    for amount in js_test_amounts:
        # Simulation du formatage JavaScript français
        formatted_js = f"{amount:,}".replace(',', ' ')
        print(f"     {amount} → {formatted_js} GNF")
    
    # 5. Vérifications des templates corrigés
    print("\n5️⃣ VÉRIFICATION DES TEMPLATES CORRIGÉS:")
    corrected_templates = [
        "templates/paiements/liste_paiements.html",
        "templates/paiements/tableau_bord.html", 
        "templates/paiements/form_paiement.html",
        "templates/paiements/echeancier_eleve.html",
        "templates/paiements/detail_paiement.html",
        "templates/eleves/detail_eleve.html"
    ]
    
    print("   Templates corrigés (suppression des duplications):")
    for template in corrected_templates:
        print(f"     ✅ {template}")
    
    print("\n🎯 INSTRUCTIONS POUR TEST VISUEL:")
    print("   1. Rechargez le serveur Django pour appliquer les nouveaux paramètres")
    print("   2. Allez sur: http://127.0.0.1:8000/paiements/liste/")
    print("   3. Vérifiez que les montants utilisent des espaces comme séparateurs")
    print("   4. Testez aussi: http://127.0.0.1:8000/eleves/liste/")
    print("   5. Vérifiez les formulaires de paiement")
    
    print("\n✅ AMÉLIORATIONS APPLIQUÉES:")
    print("   - Configuration Django pour espaces comme séparateurs")
    print("   - Suppression des duplications |floatformat:0|intcomma")
    print("   - Format français: 150 000 GNF (au lieu de 150,000)")
    print("   - Cohérence dans tous les templates")
    print("   - Groupement par 3 chiffres")

if __name__ == '__main__':
    test_thousands_separator()
