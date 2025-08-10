#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnostic pour identifier le probleme avec l'enregistrement d'eleves
"""

import os
import sys
import django
from datetime import date

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from eleves.models import Eleve, Responsable, Classe, Ecole
from eleves.forms import EleveForm, ResponsableForm
from eleves.views import ajouter_eleve

def debug_enregistrement():
    print("DIAGNOSTIC COMPLET DE L'ENREGISTREMENT")
    print("=" * 60)
    
    # 1. Verifier les donnees de base
    print("\n1. VERIFICATION DES DONNEES DE BASE")
    print("-" * 40)
    
    ecole = Ecole.objects.first()
    classe = Classe.objects.first()
    responsable = Responsable.objects.first()
    
    if not all([ecole, classe, responsable]):
        print("ERREUR: Donnees manquantes")
        return False
    
    print(f"Ecole: {ecole.nom}")
    print(f"Classe: {classe.nom}")
    print(f"Responsable: {responsable.prenom} {responsable.nom}")
    
    # 2. Test du formulaire avec donnees completes
    print("\n2. TEST DU FORMULAIRE AVEC DONNEES COMPLETES")
    print("-" * 50)
    
    donnees_post = {
        'matricule': 'DEBUG001',
        'prenom': 'Debug',
        'nom': 'Test',
        'sexe': 'M',
        'date_naissance': '2015-01-01',
        'lieu_naissance': 'Conakry',
        'classe': str(classe.id),
        'date_inscription': date.today().strftime('%Y-%m-%d'),
        'statut': 'ACTIF',
        'responsable_principal': str(responsable.id),
        'responsable_principal_nouveau': '',  # Pas de nouveau responsable
        'responsable_secondaire_nouveau': '',
    }
    
    print("Donnees POST simulees:")
    for key, value in donnees_post.items():
        print(f"  {key}: {value}")
    
    # 3. Test de validation du formulaire
    print("\n3. TEST DE VALIDATION DU FORMULAIRE")
    print("-" * 40)
    
    form = EleveForm(data=donnees_post)
    
    if form.is_valid():
        print("OK - Formulaire principal valide")
        print("Donnees nettoyees:")
        for field, value in form.cleaned_data.items():
            print(f"  {field}: {value}")
    else:
        print("ERREUR - Formulaire principal invalide:")
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
        return False
    
    # 4. Simulation de la vue avec une requete POST
    print("\n4. SIMULATION DE LA VUE AVEC REQUETE POST")
    print("-" * 45)
    
    try:
        # Creer un utilisateur de test
        user, created = User.objects.get_or_create(
            username='debug_user',
            defaults={'email': 'debug@test.com'}
        )
        print(f"Utilisateur: {user.username}")
        
        # Creer une requete POST simulee
        factory = RequestFactory()
        request = factory.post('/eleves/ajouter/', data=donnees_post)
        request.user = user
        
        # Ajouter les sessions et messages
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        messages = FallbackStorage(request)
        request._messages = messages
        
        print("Requete POST simulee creee")
        
        # Compter les eleves avant
        count_avant = Eleve.objects.count()
        print(f"Nombre d'eleves avant: {count_avant}")
        
        # Appeler la vue
        print("Appel de la vue ajouter_eleve...")
        response = ajouter_eleve(request)
        
        # Compter les eleves apres
        count_apres = Eleve.objects.count()
        print(f"Nombre d'eleves apres: {count_apres}")
        
        if count_apres > count_avant:
            print("SUCCES - Eleve cree!")
            nouvel_eleve = Eleve.objects.latest('id')
            print(f"Nouvel eleve: {nouvel_eleve.prenom} {nouvel_eleve.nom} (ID: {nouvel_eleve.id})")
            
            # Nettoyer
            nouvel_eleve.delete()
            print("Donnees de test nettoyees")
            
        else:
            print("PROBLEME - Aucun eleve cree")
            print(f"Code de reponse: {response.status_code}")
            
            # Verifier les messages d'erreur
            storage = messages._get_storage()
            if hasattr(storage, '_queued_messages'):
                print("Messages:")
                for message in storage._queued_messages:
                    print(f"  {message.level_tag}: {message.message}")
        
        return count_apres > count_avant
        
    except Exception as e:
        print(f"ERREUR lors de la simulation: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. Test de creation directe
    print("\n5. TEST DE CREATION DIRECTE")
    print("-" * 30)
    
    try:
        eleve_direct = Eleve.objects.create(
            matricule='DIRECT001',
            prenom='Direct',
            nom='Test',
            sexe='M',
            date_naissance=date(2015, 1, 1),
            lieu_naissance='Conakry',
            classe=classe,
            date_inscription=date.today(),
            statut='ACTIF',
            responsable_principal=responsable,
            cree_par=user
        )
        
        print(f"SUCCES - Creation directe: {eleve_direct.prenom} {eleve_direct.nom}")
        
        # Nettoyer
        eleve_direct.delete()
        print("Donnees de test nettoyees")
        
        return True
        
    except Exception as e:
        print(f"ERREUR creation directe: {e}")
        return False

if __name__ == '__main__':
    try:
        success = debug_enregistrement()
        
        print("\n" + "=" * 60)
        if success:
            print("DIAGNOSTIC: Le systeme peut creer des eleves")
            print("Le probleme est probablement dans l'interface utilisateur")
            print("\nRECOMMANDATIONS:")
            print("1. Verifier que le formulaire HTML se soumet correctement")
            print("2. Verifier les champs caches et les noms des champs")
            print("3. Verifier la validation JavaScript")
            print("4. Tester avec les outils de developpement du navigateur")
        else:
            print("DIAGNOSTIC: Il y a un probleme avec la creation d'eleves")
            print("Le probleme est dans le code Django")
            
    except Exception as e:
        print(f"ERREUR GENERALE: {e}")
        import traceback
        traceback.print_exc()
