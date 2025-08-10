#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test pour verifier la creation d'un nouveau responsable dans le formulaire d'ajout d'eleve
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

def test_nouveau_responsable():
    print("TEST CREATION NOUVEAU RESPONSABLE")
    print("=" * 50)
    
    # Donnees de base
    ecole = Ecole.objects.first()
    classe = Classe.objects.first()
    
    print(f"Ecole: {ecole.nom}")
    print(f"Classe: {classe.nom}")
    
    # Compter avant
    count_eleves_avant = Eleve.objects.count()
    count_responsables_avant = Responsable.objects.count()
    
    print(f"Eleves avant: {count_eleves_avant}")
    print(f"Responsables avant: {count_responsables_avant}")
    
    # Donnees POST avec nouveau responsable
    import random
    matricule_unique = f'NEWRESP{random.randint(100, 999)}'
    donnees_post = {
        # Donnees eleve
        'matricule': matricule_unique,
        'prenom': 'Test',
        'nom': 'NouveauResp',
        'sexe': 'M',
        'date_naissance': '2015-01-01',
        'lieu_naissance': 'Conakry',
        'classe': str(classe.id),
        'date_inscription': date.today().strftime('%Y-%m-%d'),
        'statut': 'ACTIF',
        
        # Indiquer qu'on cree un nouveau responsable
        'responsable_principal_nouveau': 'on',
        
        # Donnees du nouveau responsable (avec prefix)
        'resp_principal-prenom': 'Papa',
        'resp_principal-nom': 'Nouveau',
        'resp_principal-relation': 'PERE',
        'resp_principal-telephone': '+224123456789',
        'resp_principal-email': 'papa.nouveau@test.com',
        'resp_principal-adresse': 'Adresse Papa Nouveau',
        'resp_principal-profession': 'Ingenieur',
        
        # Pas de responsable secondaire
        'responsable_secondaire_nouveau': '',
    }
    
    print("\nDonnees POST avec nouveau responsable:")
    for key, value in donnees_post.items():
        print(f"  {key}: {value}")
    
    try:
        # Creer utilisateur
        user, created = User.objects.get_or_create(
            username='test_nouveau_resp',
            defaults={'email': 'test@nouveauresp.com'}
        )
        
        # Creer requete POST
        factory = RequestFactory()
        request = factory.post('/eleves/ajouter/', data=donnees_post)
        request.user = user
        
        # Ajouter sessions et messages
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        messages = FallbackStorage(request)
        request._messages = messages
        
        print("\nAppel de la vue ajouter_eleve...")
        response = ajouter_eleve(request)
        
        # Compter apres
        count_eleves_apres = Eleve.objects.count()
        count_responsables_apres = Responsable.objects.count()
        
        print(f"Eleves apres: {count_eleves_apres}")
        print(f"Responsables apres: {count_responsables_apres}")
        
        if count_eleves_apres > count_eleves_avant and count_responsables_apres > count_responsables_avant:
            print("SUCCES - Eleve et responsable crees!")
            
            # Trouver les nouveaux objets
            nouvel_eleve = Eleve.objects.latest('id')
            nouveau_responsable = Responsable.objects.latest('id')
            
            print(f"Nouvel eleve: {nouvel_eleve.prenom} {nouvel_eleve.nom}")
            print(f"Nouveau responsable: {nouveau_responsable.prenom} {nouveau_responsable.nom}")
            print(f"Relation: {nouvel_eleve.responsable_principal.prenom} {nouvel_eleve.responsable_principal.nom}")
            
            # Nettoyer
            nouvel_eleve.delete()
            nouveau_responsable.delete()
            print("Donnees de test nettoyees")
            
            return True
        else:
            print("PROBLEME - Creation incomplete")
            print(f"Code reponse: {response.status_code}")
            
            # Verifier les messages
            storage = messages._get_storage()
            if hasattr(storage, '_queued_messages'):
                print("Messages:")
                for message in storage._queued_messages:
                    print(f"  {message.level_tag}: {message.message}")
            
            return False
            
    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_formulaires_separes():
    print("\nTEST FORMULAIRES SEPARES")
    print("-" * 30)
    
    # Test du formulaire eleve avec matricule unique
    import random
    matricule_unique = f'TEST{random.randint(1000, 9999)}'
    donnees_eleve = {
        'matricule': matricule_unique,
        'prenom': 'Test',
        'nom': 'Eleve',
        'sexe': 'M',
        'date_naissance': date(2015, 1, 1),
        'lieu_naissance': 'Conakry',
        'classe': Classe.objects.first().id,
        'date_inscription': date.today(),
        'statut': 'ACTIF',
        'responsable_principal': '',  # Sera rempli apres
    }
    
    # Test du formulaire responsable
    donnees_responsable = {
        'prenom': 'Papa',
        'nom': 'Test',
        'relation': 'PERE',
        'telephone': '+224123456789',
        'email': 'papa@test.com',
        'adresse': 'Adresse Papa',
        'profession': 'Ingenieur'
    }
    
    try:
        # Test responsable
        form_resp = ResponsableForm(data=donnees_responsable, prefix='resp_principal')
        if form_resp.is_valid():
            print("OK - Formulaire responsable valide")
            responsable = form_resp.save()
            print(f"Responsable cree: {responsable.prenom} {responsable.nom}")
            
            # Test eleve avec ce responsable
            donnees_eleve['responsable_principal'] = responsable.id
            form_eleve = EleveForm(data=donnees_eleve)
            
            if form_eleve.is_valid():
                print("OK - Formulaire eleve valide")
                
                user = User.objects.get_or_create(username='test_sep')[0]
                eleve = form_eleve.save(commit=False)
                eleve.cree_par = user
                eleve.save()
                
                print(f"Eleve cree: {eleve.prenom} {eleve.nom}")
                print(f"Avec responsable: {eleve.responsable_principal.prenom}")
                
                # Nettoyer
                eleve.delete()
                responsable.delete()
                print("Donnees nettoyees")
                
                return True
            else:
                print("ERREUR - Formulaire eleve invalide:")
                for field, errors in form_eleve.errors.items():
                    print(f"  {field}: {errors}")
        else:
            print("ERREUR - Formulaire responsable invalide:")
            for field, errors in form_resp.errors.items():
                print(f"  {field}: {errors}")
        
        return False
        
    except Exception as e:
        print(f"ERREUR: {e}")
        return False

if __name__ == '__main__':
    try:
        print("TEST COMPLET - CREATION NOUVEAU RESPONSABLE")
        print("=" * 60)
        
        # Test 1: Formulaires separes
        success1 = test_formulaires_separes()
        
        # Test 2: Vue complete
        success2 = test_nouveau_responsable()
        
        print("\n" + "=" * 60)
        if success1 and success2:
            print("RESULTAT: TOUS LES TESTS PASSES")
            print("Le formulaire devrait fonctionner pour creer un nouveau responsable")
        else:
            print("RESULTAT: PROBLEMES DETECTES")
            if not success1:
                print("- Probleme avec les formulaires separes")
            if not success2:
                print("- Probleme avec la vue complete")
                
    except Exception as e:
        print(f"ERREUR GENERALE: {e}")
        sys.exit(1)
