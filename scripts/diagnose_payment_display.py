#!/usr/bin/env python
"""
Script de diagnostic avancé pour identifier pourquoi les paiements EN_ATTENTE ne s'affichent pas
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import Paiement
from paiements.forms import RechercheForm
from paiements.views import liste_paiements
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q

def diagnose_payment_display():
    """Diagnostic complet du problème d'affichage des paiements"""
    
    print("🔍 DIAGNOSTIC AVANCÉ - AFFICHAGE DES PAIEMENTS")
    print("=" * 60)
    
    # 1. Vérifier les paiements EN_ATTENTE dans la DB
    print("\n1️⃣ VÉRIFICATION BASE DE DONNÉES:")
    paiements_attente = Paiement.objects.filter(statut='EN_ATTENTE')
    print(f"   Nombre total de paiements EN_ATTENTE: {paiements_attente.count()}")
    
    for p in paiements_attente:
        print(f"   - {p.numero_recu}: {p.eleve.nom_complet} ({p.eleve.classe.ecole.nom}) - {p.montant} GNF")
    
    # 2. Tester le formulaire avec différents paramètres
    print("\n2️⃣ TEST DU FORMULAIRE DE RECHERCHE:")
    
    # Test 1: Seulement le statut
    form_data_1 = {'statut': 'EN_ATTENTE'}
    form1 = RechercheForm(form_data_1)
    print(f"   Test 1 - Statut seulement:")
    print(f"     Form valid: {form1.is_valid()}")
    if form1.is_valid():
        print(f"     Cleaned data: {form1.cleaned_data}")
    else:
        print(f"     Form errors: {form1.errors}")
    
    # Test 2: Statut + école vide
    form_data_2 = {'statut': 'EN_ATTENTE', 'ecole': ''}
    form2 = RechercheForm(form_data_2)
    print(f"   Test 2 - Statut + école vide:")
    print(f"     Form valid: {form2.is_valid()}")
    if form2.is_valid():
        print(f"     Cleaned data: {form2.cleaned_data}")
    else:
        print(f"     Form errors: {form2.errors}")
    
    # 3. Simuler exactement la logique de la vue
    print("\n3️⃣ SIMULATION DE LA VUE liste_paiements:")
    
    # Données GET simulées
    get_params = {'statut': 'EN_ATTENTE'}
    form = RechercheForm(get_params)
    
    print(f"   GET params: {get_params}")
    print(f"   Form valid: {form.is_valid()}")
    
    if form.is_valid():
        print(f"   Cleaned data: {form.cleaned_data}")
        
        # Reproduire exactement la logique de la vue
        paiements = Paiement.objects.select_related(
            'eleve', 'type_paiement', 'mode_paiement', 'valide_par'
        ).order_by('-date_paiement')
        
        print(f"   Paiements initiaux: {paiements.count()}")
        
        # Appliquer les filtres un par un
        if form.cleaned_data.get('recherche'):
            recherche = form.cleaned_data['recherche']
            paiements = paiements.filter(
                Q(eleve__nom__icontains=recherche) |
                Q(eleve__prenom__icontains=recherche) |
                Q(eleve__matricule__icontains=recherche) |
                Q(numero_recu__icontains=recherche)
            )
            print(f"   Après filtre recherche: {paiements.count()}")
        
        if form.cleaned_data.get('statut'):
            print(f"   Filtrage par statut: {form.cleaned_data['statut']}")
            paiements = paiements.filter(statut=form.cleaned_data['statut'])
            print(f"   Après filtre statut: {paiements.count()}")
        
        if form.cleaned_data.get('type_paiement'):
            paiements = paiements.filter(type_paiement=form.cleaned_data['type_paiement'])
            print(f"   Après filtre type: {paiements.count()}")
        
        if form.cleaned_data.get('date_debut'):
            paiements = paiements.filter(date_paiement__gte=form.cleaned_data['date_debut'])
            print(f"   Après filtre date_debut: {paiements.count()}")
        
        if form.cleaned_data.get('date_fin'):
            paiements = paiements.filter(date_paiement__lte=form.cleaned_data['date_fin'])
            print(f"   Après filtre date_fin: {paiements.count()}")
        
        if form.cleaned_data.get('ecole'):
            print(f"   Filtrage par école: {form.cleaned_data['ecole']}")
            paiements = paiements.filter(eleve__classe__ecole=form.cleaned_data['ecole'])
            print(f"   Après filtre école: {paiements.count()}")
        
        print(f"   RÉSULTAT FINAL: {paiements.count()} paiement(s)")
        
        # Afficher les paiements trouvés
        for p in paiements:
            print(f"     - {p.numero_recu}: {p.eleve.nom_complet} - {p.statut}")
        
        # Test de pagination
        paginator = Paginator(paiements, 20)
        page_obj = paginator.get_page(1)
        print(f"   Page 1 contient: {len(page_obj)} paiement(s)")
        
    else:
        print(f"   Form errors: {form.errors}")
    
    # 4. Vérifier la requête SQL générée
    print("\n4️⃣ VÉRIFICATION REQUÊTE SQL:")
    try:
        from django.db import connection
        
        # Requête directe
        direct_query = Paiement.objects.filter(statut='EN_ATTENTE')
        print(f"   Requête directe: {direct_query.count()} résultats")
        print(f"   SQL: {direct_query.query}")
        
        # Requête avec select_related (comme dans la vue)
        view_query = Paiement.objects.select_related(
            'eleve', 'type_paiement', 'mode_paiement', 'valide_par'
        ).filter(statut='EN_ATTENTE')
        print(f"   Requête avec select_related: {view_query.count()} résultats")
        
    except Exception as e:
        print(f"   Erreur SQL: {e}")
    
    # 5. Vérifier les relations
    print("\n5️⃣ VÉRIFICATION DES RELATIONS:")
    for p in paiements_attente:
        try:
            print(f"   Paiement {p.numero_recu}:")
            print(f"     - Élève: {p.eleve.nom_complet} ✅")
            print(f"     - Classe: {p.eleve.classe.nom} ✅")
            print(f"     - École: {p.eleve.classe.ecole.nom} ✅")
            print(f"     - Type: {p.type_paiement.nom} ✅")
            print(f"     - Mode: {p.mode_paiement.nom} ✅")
        except Exception as e:
            print(f"     ❌ Erreur relation: {e}")

if __name__ == '__main__':
    diagnose_payment_display()
