#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test pour reproduire le problème de mise à jour des statuts dans la liste des élèves
"""

import os
import sys
import django
from datetime import date

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory, Client
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from eleves.models import Eleve, Responsable, Classe, Ecole
from eleves.forms import EleveForm
from eleves.views import modifier_eleve, liste_eleves

def test_modification_statut_et_liste():
    print("TEST MODIFICATION STATUT ET MISE À JOUR LISTE")
    print("=" * 60)
    
    # Trouver un élève pour le test
    eleve_test = Eleve.objects.first()
    if not eleve_test:
        print("❌ Aucun élève trouvé pour le test")
        return False
    
    print(f"Élève de test: {eleve_test.prenom} {eleve_test.nom} (ID: {eleve_test.id})")
    print(f"Statut actuel: {eleve_test.statut}")
    
    # Sauvegarder le statut original
    statut_original = eleve_test.statut
    
    try:
        # Étape 1: Modifier le statut directement en base
        print("\n" + "-" * 40)
        print("ÉTAPE 1: Modification directe en base")
        print("-" * 40)
        
        nouveau_statut = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        eleve_test.statut = nouveau_statut
        eleve_test.save()
        
        print(f"Statut modifié en base: {eleve_test.statut}")
        
        # Vérifier en base
        eleve_verifie = Eleve.objects.get(id=eleve_test.id)
        print(f"Statut vérifié en base: {eleve_verifie.statut}")
        
        # Étape 2: Test de la vue liste_eleves
        print("\n" + "-" * 40)
        print("ÉTAPE 2: Test vue liste_eleves")
        print("-" * 40)
        
        # Créer utilisateur de test
        user, created = User.objects.get_or_create(
            username='test_statut_liste',
            defaults={'email': 'test@statut.com'}
        )
        
        # Créer requête GET pour la liste
        factory = RequestFactory()
        request = factory.get('/eleves/')
        request.user = user
        
        # Ajouter sessions
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        print("Appel de la vue liste_eleves...")
        response = liste_eleves(request)
        
        # Analyser la réponse
        if response.status_code == 200:
            print("✅ Vue liste_eleves répond correctement")
            
            # Vérifier le contexte
            context = response.context_data if hasattr(response, 'context_data') else {}
            if 'page_obj' in context:
                eleves_dans_liste = list(context['page_obj'])
                eleve_trouve = None
                
                for eleve in eleves_dans_liste:
                    if eleve.id == eleve_test.id:
                        eleve_trouve = eleve
                        break
                
                if eleve_trouve:
                    print(f"✅ Élève trouvé dans la liste")
                    print(f"Statut dans la liste: {eleve_trouve.statut}")
                    
                    if eleve_trouve.statut == nouveau_statut:
                        print("✅ Statut correctement mis à jour dans la liste")
                    else:
                        print(f"❌ Statut non mis à jour dans la liste: {eleve_trouve.statut} != {nouveau_statut}")
                else:
                    print("❌ Élève non trouvé dans la liste")
            else:
                print("❌ Pas de page_obj dans le contexte")
        else:
            print(f"❌ Vue liste_eleves erreur: {response.status_code}")
        
        # Étape 3: Test avec modification via formulaire
        print("\n" + "-" * 40)
        print("ÉTAPE 3: Modification via formulaire")
        print("-" * 40)
        
        # Préparer données de modification
        statut_final = 'EXCLU' if nouveau_statut != 'EXCLU' else 'ACTIF'
        
        donnees_modification = {
            'matricule': eleve_test.matricule,
            'prenom': eleve_test.prenom,
            'nom': eleve_test.nom,
            'sexe': eleve_test.sexe,
            'date_naissance': eleve_test.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': eleve_test.lieu_naissance,
            'classe': str(eleve_test.classe.id),
            'date_inscription': eleve_test.date_inscription.strftime('%Y-%m-%d'),
            'statut': statut_final,  # Nouveau statut
            'responsable_principal': str(eleve_test.responsable_principal.id),
            'responsable_secondaire': str(eleve_test.responsable_secondaire.id) if eleve_test.responsable_secondaire else '',
        }
        
        print(f"Modification du statut vers: {statut_final}")
        
        # Créer requête POST pour modification
        request_post = factory.post(f'/eleves/{eleve_test.id}/modifier/', data=donnees_modification)
        request_post.user = user
        
        # Ajouter sessions et messages
        middleware.process_request(request_post)
        request_post.session.save()
        
        messages = FallbackStorage(request_post)
        request_post._messages = messages
        
        print("Appel de la vue modifier_eleve...")
        response_modif = modifier_eleve(request_post, eleve_test.id)
        
        # Vérifier la modification
        eleve_test.refresh_from_db()
        print(f"Statut après modification via formulaire: {eleve_test.statut}")
        
        if eleve_test.statut == statut_final:
            print("✅ Modification via formulaire réussie")
        else:
            print("❌ Modification via formulaire échouée")
        
        # Étape 4: Re-test de la liste après modification formulaire
        print("\n" + "-" * 40)
        print("ÉTAPE 4: Re-test liste après modification formulaire")
        print("-" * 40)
        
        # Nouvelle requête GET pour la liste
        request_liste2 = factory.get('/eleves/')
        request_liste2.user = user
        middleware.process_request(request_liste2)
        request_liste2.session.save()
        
        response_liste2 = liste_eleves(request_liste2)
        
        if response_liste2.status_code == 200:
            print("✅ Vue liste_eleves répond après modification")
            
            # Analyser le nouveau contexte
            context2 = response_liste2.context_data if hasattr(response_liste2, 'context_data') else {}
            if 'page_obj' in context2:
                eleves_dans_liste2 = list(context2['page_obj'])
                eleve_trouve2 = None
                
                for eleve in eleves_dans_liste2:
                    if eleve.id == eleve_test.id:
                        eleve_trouve2 = eleve
                        break
                
                if eleve_trouve2:
                    print(f"✅ Élève trouvé dans la liste mise à jour")
                    print(f"Statut final dans la liste: {eleve_trouve2.statut}")
                    
                    if eleve_trouve2.statut == statut_final:
                        print("✅ SUCCÈS - Statut correctement mis à jour dans la liste après modification")
                        return True
                    else:
                        print(f"❌ PROBLÈME - Statut non mis à jour dans la liste: {eleve_trouve2.statut} != {statut_final}")
                        return False
                else:
                    print("❌ Élève non trouvé dans la liste mise à jour")
                    return False
        
        return False
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restaurer le statut original
        print("\n" + "-" * 40)
        print("RESTAURATION STATUT ORIGINAL")
        print("-" * 40)
        
        try:
            eleve_test.statut = statut_original
            eleve_test.save()
            print(f"✅ Statut restauré: {eleve_test.statut}")
        except Exception as e:
            print(f"❌ Erreur lors de la restauration: {e}")

def test_avec_client_django():
    print("\n" + "=" * 60)
    print("TEST AVEC CLIENT DJANGO (SIMULATION NAVIGATEUR)")
    print("=" * 60)
    
    # Utiliser le client Django pour simuler un vrai navigateur
    client = Client()
    
    # Créer utilisateur et se connecter
    user, created = User.objects.get_or_create(
        username='test_client_statut',
        defaults={'email': 'test@client.com', 'password': 'testpass123'}
    )
    
    if created:
        user.set_password('testpass123')
        user.save()
    
    # Se connecter
    login_success = client.login(username='test_client_statut', password='testpass123')
    print(f"Connexion réussie: {login_success}")
    
    if not login_success:
        print("❌ Impossible de se connecter, test abandonné")
        return False
    
    # Trouver un élève
    eleve_test = Eleve.objects.first()
    if not eleve_test:
        print("❌ Aucun élève pour le test")
        return False
    
    print(f"Test avec élève: {eleve_test.prenom} {eleve_test.nom}")
    statut_original = eleve_test.statut
    
    try:
        # Étape 1: Voir la liste avant modification
        print("\nÉtape 1: Liste avant modification")
        response_avant = client.get('/eleves/')
        print(f"Status code: {response_avant.status_code}")
        
        if response_avant.status_code == 200:
            # Chercher l'élève dans le contenu HTML
            content_avant = response_avant.content.decode('utf-8')
            if eleve_test.matricule in content_avant:
                print(f"✅ Élève trouvé dans la liste HTML")
                if eleve_test.statut in content_avant:
                    print(f"✅ Statut {eleve_test.statut} trouvé dans HTML")
            else:
                print("❌ Élève non trouvé dans la liste HTML")
        
        # Étape 2: Modifier l'élève via POST
        print(f"\nÉtape 2: Modification du statut")
        nouveau_statut = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        
        donnees_modif = {
            'matricule': eleve_test.matricule,
            'prenom': eleve_test.prenom,
            'nom': eleve_test.nom,
            'sexe': eleve_test.sexe,
            'date_naissance': eleve_test.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': eleve_test.lieu_naissance,
            'classe': str(eleve_test.classe.id),
            'date_inscription': eleve_test.date_inscription.strftime('%Y-%m-%d'),
            'statut': nouveau_statut,
            'responsable_principal': str(eleve_test.responsable_principal.id),
            'responsable_secondaire': str(eleve_test.responsable_secondaire.id) if eleve_test.responsable_secondaire else '',
        }
        
        response_modif = client.post(f'/eleves/{eleve_test.id}/modifier/', data=donnees_modif)
        print(f"Status code modification: {response_modif.status_code}")
        
        # Vérifier la redirection
        if response_modif.status_code == 302:
            print(f"✅ Redirection après modification: {response_modif.url}")
        
        # Vérifier en base
        eleve_test.refresh_from_db()
        print(f"Statut en base après modification: {eleve_test.statut}")
        
        # Étape 3: Voir la liste après modification
        print(f"\nÉtape 3: Liste après modification")
        response_apres = client.get('/eleves/')
        print(f"Status code: {response_apres.status_code}")
        
        if response_apres.status_code == 200:
            content_apres = response_apres.content.decode('utf-8')
            if eleve_test.matricule in content_apres:
                print(f"✅ Élève trouvé dans la liste HTML après modification")
                if nouveau_statut in content_apres:
                    print(f"✅ SUCCÈS - Nouveau statut {nouveau_statut} trouvé dans HTML")
                    return True
                else:
                    print(f"❌ PROBLÈME - Nouveau statut {nouveau_statut} NON trouvé dans HTML")
                    # Chercher l'ancien statut
                    if statut_original in content_apres:
                        print(f"❌ Ancien statut {statut_original} encore présent dans HTML")
                    return False
            else:
                print("❌ Élève non trouvé dans la liste HTML après modification")
                return False
        
        return False
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restaurer
        eleve_test.statut = statut_original
        eleve_test.save()
        print(f"✅ Statut restauré: {statut_original}")

if __name__ == '__main__':
    try:
        print("TEST COMPLET - PROBLÈME MISE À JOUR STATUTS LISTE")
        print("=" * 70)
        
        # Test 1: Avec RequestFactory
        success1 = test_modification_statut_et_liste()
        
        # Test 2: Avec Client Django
        success2 = test_avec_client_django()
        
        print("\n" + "=" * 70)
        if success1 and success2:
            print("✅ AUCUN PROBLÈME DÉTECTÉ")
            print("Les statuts se mettent à jour correctement dans la liste")
        else:
            print("❌ PROBLÈME CONFIRMÉ")
            if not success1:
                print("- Problème avec RequestFactory")
            if not success2:
                print("- Problème avec Client Django (simulation navigateur)")
                
    except Exception as e:
        print(f"ERREUR GÉNÉRALE: {e}")
        sys.exit(1)
