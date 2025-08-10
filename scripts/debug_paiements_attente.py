#!/usr/bin/env python
"""
Script pour déboguer l'affichage des paiements en attente
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

def debug_paiements_attente():
    """Debug l'affichage des paiements en attente"""
    
    print("🔍 DÉBOGAGE DES PAIEMENTS EN ATTENTE")
    print("=" * 50)
    
    # 1. Vérifier les paiements en attente dans la DB
    print("\n1️⃣ VÉRIFICATION BASE DE DONNÉES:")
    paiements_attente = Paiement.objects.filter(statut='EN_ATTENTE')
    print(f"   Nombre de paiements EN_ATTENTE: {paiements_attente.count()}")
    
    for p in paiements_attente:
        print(f"   - {p.numero_recu}: {p.eleve.nom_complet} - {p.montant} GNF - {p.statut}")
    
    # 2. Tester le formulaire de recherche
    print("\n2️⃣ TEST DU FORMULAIRE:")
    form_data = {'statut': 'EN_ATTENTE'}
    form = RechercheForm(form_data)
    print(f"   Form data: {form.data}")
    print(f"   Form valid: {form.is_valid()}")
    
    if form.is_valid():
        print(f"   Cleaned data: {form.cleaned_data}")
        
        # 3. Simuler le filtrage de la vue
        print("\n3️⃣ SIMULATION DU FILTRAGE:")
        paiements = Paiement.objects.select_related(
            'eleve', 'type_paiement', 'mode_paiement', 'valide_par'
        ).order_by('-date_paiement')
        
        print(f"   Paiements avant filtrage: {paiements.count()}")
        
        if form.cleaned_data.get('statut'):
            paiements = paiements.filter(statut=form.cleaned_data['statut'])
            print(f"   Paiements après filtrage par statut: {paiements.count()}")
            
            for p in paiements:
                print(f"   - {p.numero_recu}: {p.eleve.nom_complet} - {p.statut}")
        
        # 4. Tester la pagination
        print("\n4️⃣ TEST DE LA PAGINATION:")
        paginator = Paginator(paiements, 20)
        page_obj = paginator.get_page(1)
        print(f"   Nombre de pages: {paginator.num_pages}")
        print(f"   Objets dans page_obj: {len(page_obj)}")
        
        for p in page_obj:
            print(f"   - {p.numero_recu}: {p.eleve.nom_complet} - {p.statut}")
    
    else:
        print(f"   Form errors: {form.errors}")
    
    # 5. Tester la vue complète
    print("\n5️⃣ TEST DE LA VUE COMPLÈTE:")
    try:
        rf = RequestFactory()
        request = rf.get('/paiements/liste/', {'statut': 'EN_ATTENTE'})
        request.user = User.objects.first()
        
        # Simuler l'authentification
        from django.contrib.auth import get_user_model
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.auth.middleware import AuthenticationMiddleware
        
        # Ajouter les middlewares nécessaires
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        
        middleware = AuthenticationMiddleware(lambda x: None)
        middleware.process_request(request)
        
        print(f"   Request GET params: {request.GET}")
        print(f"   User authenticated: {request.user.is_authenticated}")
        
        # Tester manuellement la logique de la vue
        form = RechercheForm(request.GET or None)
        paiements = Paiement.objects.select_related(
            'eleve', 'type_paiement', 'mode_paiement', 'valide_par'
        ).order_by('-date_paiement')
        
        print(f"   Form valid in view: {form.is_valid()}")
        
        if form.is_valid():
            if form.cleaned_data.get('statut'):
                paiements = paiements.filter(statut=form.cleaned_data['statut'])
                print(f"   Filtered paiements count: {paiements.count()}")
        
        paginator = Paginator(paiements, 20)
        page_obj = paginator.get_page(1)
        
        print(f"   Final page_obj count: {len(page_obj)}")
        
    except Exception as e:
        print(f"   Erreur lors du test de la vue: {e}")
    
    # 6. Vérifier le template
    print("\n6️⃣ VÉRIFICATION DU TEMPLATE:")
    template_path = r"c:\Users\faral\Desktop\GS HADJA_KANFING_DIANÉ\templates\paiements\liste_paiements.html"
    
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"   Template existe: ✅")
        print(f"   Contient 'page_obj': {'page_obj' in content}")
        print(f"   Contient 'for paiement in page_obj': {'for paiement in page_obj' in content}")
        print(f"   Contient 'EN_ATTENTE': {'EN_ATTENTE' in content}")
        print(f"   Contient 'btn-outline-success': {'btn-outline-success' in content}")
    else:
        print(f"   Template n'existe pas: ❌")

if __name__ == '__main__':
    debug_paiements_attente()
