#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test pour vérifier que la correction du problème de mise à jour des statuts fonctionne
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from eleves.models import Eleve

def test_correction_statut_liste():
    print("TEST CORRECTION - MISE À JOUR STATUT DANS LISTE")
    print("=" * 60)
    
    # Créer client et utilisateur
    client = Client()
    user, created = User.objects.get_or_create(
        username='test_correction_statut',
        defaults={'email': 'test@correction.com'}
    )
    
    if created:
        user.set_password('testpass123')
        user.save()
    
    # Se connecter
    login_success = client.login(username='test_correction_statut', password='testpass123')
    if not login_success:
        print("❌ Impossible de se connecter")
        return False
    
    print("✅ Connexion réussie")
    
    # Trouver un élève pour le test
    eleve_test = Eleve.objects.first()
    if not eleve_test:
        print("❌ Aucun élève pour le test")
        return False
    
    print(f"Élève de test: {eleve_test.prenom} {eleve_test.nom}")
    print(f"Statut actuel: {eleve_test.statut}")
    
    statut_original = eleve_test.statut
    
    try:
        # Test 1: Modification avec redirection vers détail (comportement par défaut)
        print("\n" + "-" * 50)
        print("TEST 1: Modification avec redirection vers détail")
        print("-" * 50)
        
        nouveau_statut1 = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        
        donnees_modif1 = {
            'matricule': eleve_test.matricule,
            'prenom': eleve_test.prenom,
            'nom': eleve_test.nom,
            'sexe': eleve_test.sexe,
            'date_naissance': eleve_test.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': eleve_test.lieu_naissance,
            'classe': str(eleve_test.classe.id),
            'date_inscription': eleve_test.date_inscription.strftime('%Y-%m-%d'),
            'statut': nouveau_statut1,
            'responsable_principal': str(eleve_test.responsable_principal.id),
            'responsable_secondaire': str(eleve_test.responsable_secondaire.id) if eleve_test.responsable_secondaire else '',
        }
        
        response1 = client.post(f'/eleves/{eleve_test.id}/modifier/', data=donnees_modif1)
        
        print(f"Status code: {response1.status_code}")
        if response1.status_code == 302:
            print(f"Redirection vers: {response1.url}")
            if f'/eleves/{eleve_test.id}/' in response1.url:
                print("✅ Redirection correcte vers le détail de l'élève")
            else:
                print("❌ Redirection incorrecte")
        
        # Vérifier la modification en base
        eleve_test.refresh_from_db()
        print(f"Statut après modification: {eleve_test.statut}")
        
        if eleve_test.statut == nouveau_statut1:
            print("✅ Modification réussie")
        else:
            print("❌ Modification échouée")
        
        # Test 2: Modification avec redirection vers liste
        print("\n" + "-" * 50)
        print("TEST 2: Modification avec redirection vers liste")
        print("-" * 50)
        
        nouveau_statut2 = 'EXCLU' if nouveau_statut1 != 'EXCLU' else 'ACTIF'
        
        donnees_modif2 = donnees_modif1.copy()
        donnees_modif2['statut'] = nouveau_statut2
        donnees_modif2['redirect_to_list'] = '1'  # Paramètre pour rediriger vers la liste
        
        response2 = client.post(f'/eleves/{eleve_test.id}/modifier/', data=donnees_modif2)
        
        print(f"Status code: {response2.status_code}")
        if response2.status_code == 302:
            print(f"Redirection vers: {response2.url}")
            if '/eleves/' in response2.url and f'{eleve_test.id}' not in response2.url:
                print("✅ Redirection correcte vers la liste des élèves")
            else:
                print("❌ Redirection incorrecte")
        
        # Vérifier la modification en base
        eleve_test.refresh_from_db()
        print(f"Statut après modification: {eleve_test.statut}")
        
        if eleve_test.statut == nouveau_statut2:
            print("✅ Modification réussie")
        else:
            print("❌ Modification échouée")
        
        # Test 3: Vérifier que la liste affiche le bon statut avec headers anti-cache
        print("\n" + "-" * 50)
        print("TEST 3: Vérification liste avec headers anti-cache")
        print("-" * 50)
        
        response_liste = client.get('/eleves/')
        
        print(f"Status code liste: {response_liste.status_code}")
        
        # Vérifier les headers anti-cache
        headers = response_liste.headers if hasattr(response_liste, 'headers') else response_liste
        cache_control = headers.get('Cache-Control', '')
        pragma = headers.get('Pragma', '')
        expires = headers.get('Expires', '')
        
        print(f"Cache-Control: {cache_control}")
        print(f"Pragma: {pragma}")
        print(f"Expires: {expires}")
        
        if 'no-cache' in cache_control and 'no-store' in cache_control:
            print("✅ Headers anti-cache correctement configurés")
        else:
            print("❌ Headers anti-cache manquants ou incorrects")
        
        # Vérifier le contenu HTML
        if response_liste.status_code == 200:
            content = response_liste.content.decode('utf-8')
            
            if eleve_test.matricule in content:
                print("✅ Élève trouvé dans la liste HTML")
                
                # Chercher le statut dans le HTML
                if nouveau_statut2 in content:
                    print(f"✅ SUCCÈS - Statut {nouveau_statut2} trouvé dans la liste HTML")
                    return True
                else:
                    print(f"❌ PROBLÈME - Statut {nouveau_statut2} NON trouvé dans la liste HTML")
                    
                    # Chercher les autres statuts pour diagnostic
                    for statut in ['ACTIF', 'SUSPENDU', 'EXCLU', 'TRANSFERE', 'DIPLOME']:
                        if statut in content and statut != nouveau_statut2:
                            print(f"⚠️ Statut {statut} trouvé à la place")
                    
                    return False
            else:
                print("❌ Élève non trouvé dans la liste HTML")
                return False
        else:
            print("❌ Erreur lors du chargement de la liste")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restaurer le statut original
        print("\n" + "-" * 50)
        print("RESTAURATION STATUT ORIGINAL")
        print("-" * 50)
        
        try:
            eleve_test.statut = statut_original
            eleve_test.save()
            print(f"✅ Statut restauré: {statut_original}")
        except Exception as e:
            print(f"❌ Erreur lors de la restauration: {e}")

if __name__ == '__main__':
    try:
        print("TEST CORRECTION COMPLÈTE - PROBLÈME STATUTS LISTE")
        print("=" * 70)
        
        success = test_correction_statut_liste()
        
        print("\n" + "=" * 70)
        if success:
            print("✅ CORRECTION RÉUSSIE")
            print("Le problème de mise à jour des statuts dans la liste est résolu !")
            print("")
            print("Solutions implémentées:")
            print("- Bouton 'Enregistrer et retourner à la liste' ajouté")
            print("- Headers anti-cache ajoutés à la vue liste_eleves")
            print("- Redirection conditionnelle vers la liste ou le détail")
        else:
            print("❌ PROBLÈME PERSISTANT")
            print("Des corrections supplémentaires peuvent être nécessaires")
                
    except Exception as e:
        print(f"ERREUR GÉNÉRALE: {e}")
        sys.exit(1)
