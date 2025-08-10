#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de diagnostic pour identifier pourquoi les modifications ne sont pas enregistrées
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
from eleves.forms import EleveForm

def test_diagnostic_modification_complete():
    """
    Test complet pour diagnostiquer le problème de non-enregistrement des modifications
    """
    print("=" * 80)
    print("DIAGNOSTIC COMPLET - PROBLEME DE NON-ENREGISTREMENT DES MODIFICATIONS")
    print("=" * 80)
    
    try:
        # 1. Vérification de l'élève Thierno BAH
        print("\nETAPE 1 : Verification de l'eleve Thierno BAH")
        eleve = Eleve.objects.filter(prenom="Thierno", nom="BAH").first()
        if not eleve:
            print("[ERREUR] Eleve Thierno BAH non trouve")
            return False
            
        print(f"[OK] Eleve trouve : {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
        print(f"   Matricule : {eleve.matricule}")
        print(f"   Date de naissance : {eleve.date_naissance}")
        print(f"   Lieu de naissance : {eleve.lieu_naissance}")
        print(f"   Classe : {eleve.classe}")
        print(f"   Statut : {eleve.statut}")
        
        # 2. Test du formulaire avec instance
        print("\nETAPE 2 : Test du formulaire avec instance")
        form = EleveForm(instance=eleve)
        
        if form.is_bound:
            print("[INFO] Formulaire lie (bound)")
        else:
            print("[INFO] Formulaire non lie (unbound)")
        
        print(f"[OK] Formulaire cree avec instance")
        
        # 3. Simulation d'une modification
        print("\nETAPE 3 : Simulation d'une modification")
        
        # Données de test avec une modification du lieu de naissance
        nouveau_lieu = "Kankan" if eleve.lieu_naissance != "Kankan" else "Conakry"
        
        post_data = {
            'matricule': eleve.matricule,
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': nouveau_lieu,  # MODIFICATION ICI
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d') if eleve.date_inscription else '',
            'statut': eleve.statut,
            'classe': eleve.classe.id if eleve.classe else '',
            'responsable_principal': eleve.responsable_principal.id if eleve.responsable_principal else '',
            'responsable_secondaire': eleve.responsable_secondaire.id if eleve.responsable_secondaire else '',
        }
        
        print(f"Modification testee : lieu_naissance '{eleve.lieu_naissance}' -> '{nouveau_lieu}'")
        
        # 4. Test de validation du formulaire
        print("\nETAPE 4 : Test de validation du formulaire")
        form_post = EleveForm(data=post_data, instance=eleve)
        
        if form_post.is_valid():
            print("[OK] Formulaire valide")
            
            # Sauvegarde
            eleve_modifie = form_post.save()
            print(f"[OK] Formulaire sauvegarde")
            print(f"   Nouveau lieu de naissance : {eleve_modifie.lieu_naissance}")
            
            # Vérification en base
            eleve_db = Eleve.objects.get(id=eleve.id)
            print(f"   Lieu en base apres modification : {eleve_db.lieu_naissance}")
            
            if eleve_db.lieu_naissance == nouveau_lieu:
                print("[OK] Modification PERSISTEE en base de donnees")
            else:
                print("[ERREUR] Modification NON persistee en base de donnees")
                return False
                
        else:
            print("[ERREUR] Formulaire invalide :")
            for field, errors in form_post.errors.items():
                print(f"   {field}: {errors}")
            return False
        
        # 5. Test via la vue Django
        print("\nETAPE 5 : Test via la vue Django")
        
        client = Client()
        user = User.objects.filter(username='LENO').first()
        if not user:
            user = User.objects.create_user(username='test_user', password='testpass')
        
        client.force_login(user)
        
        # Restauration de la valeur originale pour le test
        eleve.lieu_naissance = "Conakry"
        eleve.save()
        
        # Test POST vers la vue
        nouveau_lieu_test = "Mamou"
        post_data['lieu_naissance'] = nouveau_lieu_test
        
        url = f'/eleves/{eleve.id}/modifier/'
        print(f"URL testee : {url}")
        
        response = client.post(url, data=post_data)
        print(f"Code de reponse : {response.status_code}")
        
        if response.status_code in [200, 302]:
            print("[OK] Requete POST traitee")
            
            # Vérification en base après POST via vue
            eleve_apres_vue = Eleve.objects.get(id=eleve.id)
            print(f"Lieu apres POST via vue : {eleve_apres_vue.lieu_naissance}")
            
            if eleve_apres_vue.lieu_naissance == nouveau_lieu_test:
                print("[OK] Modification via vue REUSSIE")
            else:
                print("[ERREUR] Modification via vue ECHOUEE")
                print(f"   Attendu : {nouveau_lieu_test}")
                print(f"   Trouve : {eleve_apres_vue.lieu_naissance}")
                return False
        else:
            print(f"[ERREUR] Erreur HTTP : {response.status_code}")
            if hasattr(response, 'content'):
                print(f"Contenu de la reponse : {response.content[:500]}")
            return False
        
        # 6. Vérification des champs du formulaire HTML
        print("\nETAPE 6 : Verification des champs du formulaire HTML")
        
        # Test GET pour voir le formulaire
        response_get = client.get(url)
        if response_get.status_code == 200:
            content = response_get.content.decode('utf-8')
            
            # Vérification de la présence des champs critiques
            champs_critiques = ['matricule', 'prenom', 'nom', 'date_naissance', 'lieu_naissance']
            for champ in champs_critiques:
                if f'name="{champ}"' in content:
                    print(f"[OK] Champ '{champ}' present dans le HTML")
                else:
                    print(f"[ERREUR] Champ '{champ}' ABSENT du HTML")
                    return False
            
            # Vérification du token CSRF
            if 'csrfmiddlewaretoken' in content:
                print("[OK] Token CSRF present")
            else:
                print("[ERREUR] Token CSRF ABSENT")
                return False
                
        else:
            print(f"[ERREUR] Impossible de recuperer le formulaire : {response_get.status_code}")
            return False
        
        print("\n" + "=" * 80)
        print("RESULTAT FINAL : DIAGNOSTIC COMPLETE")
        print("[OK] Le formulaire fonctionne correctement au niveau technique")
        print("[OK] Les modifications sont bien persistees en base de donnees")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n[ERREUR] Erreur lors du diagnostic : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_verification_template():
    """
    Vérification du template utilisé
    """
    print("\n" + "=" * 80)
    print("VERIFICATION DU TEMPLATE")
    print("=" * 80)
    
    try:
        client = Client()
        user = User.objects.first()
        if user:
            client.force_login(user)
        
        eleve = Eleve.objects.filter(prenom="Thierno", nom="BAH").first()
        if not eleve:
            print("[ERREUR] Eleve non trouve pour test template")
            return False
        
        url = f'/eleves/{eleve.id}/modifier/'
        response = client.get(url)
        
        if response.status_code == 200:
            content = response.content.decode('utf-8')
            
            print(f"Template utilise detecte :")
            if 'modificationForm' in content:
                print("   [INFO] Template nouveau detecte (ID: modificationForm)")
            elif 'eleveForm' in content:
                print("   [INFO] Template ancien detecte (ID: eleveForm)")
            else:
                print("   [ATTENTION] Template non identifie")
            
            # Vérification des boutons d'action
            if 'name="action"' in content:
                print("   [OK] Boutons avec attribut 'action' detectes")
            else:
                print("   [INFO] Boutons sans attribut 'action'")
            
            return True
        else:
            print(f"[ERREUR] Impossible d'acceder au template : {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERREUR] Erreur verification template : {str(e)}")
        return False

if __name__ == "__main__":
    print("LANCEMENT DU DIAGNOSTIC - PROBLEME DE NON-ENREGISTREMENT")
    
    # Test 1 : Diagnostic complet
    test1_result = test_diagnostic_modification_complete()
    
    # Test 2 : Vérification template
    test2_result = test_verification_template()
    
    print("\n" + "=" * 80)
    print("RESUME DU DIAGNOSTIC")
    print("=" * 80)
    print(f"Test 1 - Diagnostic complet : {'[OK] REUSSI' if test1_result else '[ERREUR] ECHOUE'}")
    print(f"Test 2 - Verification template : {'[OK] REUSSI' if test2_result else '[ERREUR] ECHOUE'}")
    
    if test1_result and test2_result:
        print("\nCONCLUSION : Le systeme technique fonctionne")
        print("[INFO] Le probleme peut etre lie a l'interface utilisateur ou au template")
    else:
        print("\nCONCLUSION : Problemes techniques detectes")
        print("[ATTENTION] Verification necessaire du code de sauvegarde")
    
    print("=" * 80)
