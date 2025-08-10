#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test complet pour vérifier que les modifications de statut sont bien persistées en base de données
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

def test_modification_statut_persistence():
    """
    Test complet pour vérifier que les modifications de statut 
    sont bien appliquées et persistées dans la base de données
    """
    print("=" * 80)
    print("TEST DE VERIFICATION - PERSISTANCE DES MODIFICATIONS DE STATUT")
    print("=" * 80)
    
    try:
        # 1. Récupération d'un élève existant
        print("\nETAPE 1 : Recuperation d'un eleve existant")
        eleve = Eleve.objects.first()
        if not eleve:
            print("❌ Aucun élève trouvé dans la base de données")
            return False
            
        print(f"[OK] Eleve trouve : {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
        print(f"   Statut actuel : {eleve.statut}")
        
        # 2. Sauvegarde du statut original
        statut_original = eleve.statut
        print(f"   Statut original sauvegardé : {statut_original}")
        
        # 3. Modification du statut
        print("\nETAPE 2 : Modification du statut")
        nouveau_statut = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        print(f"   Nouveau statut à appliquer : {nouveau_statut}")
        
        # Test avec le formulaire Django
        form_data = {
            'matricule': eleve.matricule,
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'statut': nouveau_statut,  # ← Modification du statut
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d'),
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d'),
            'classe': eleve.classe.id if eleve.classe else '',
            'responsable_principal': eleve.responsable_principal.id if eleve.responsable_principal else '',
            'responsable_secondaire': eleve.responsable_secondaire.id if eleve.responsable_secondaire else '',
        }
        
        form = EleveForm(data=form_data, instance=eleve)
        
        if form.is_valid():
            print("[OK] Formulaire valide")
            eleve_modifie = form.save()
            print(f"[OK] Eleve sauvegarde avec nouveau statut : {eleve_modifie.statut}")
        else:
            print("[ERREUR] Formulaire invalide :")
            for field, errors in form.errors.items():
                print(f"   - {field}: {errors}")
            return False
        
        # 4. Vérification immédiate en mémoire
        print("\nETAPE 3 : Verification immediate (objet en memoire)")
        print(f"   Statut de l'objet modifié : {eleve_modifie.statut}")
        print(f"   Statut de l'objet original : {eleve.statut}")
        
        if eleve_modifie.statut == nouveau_statut:
            print("[OK] Modification appliquee en memoire")
        else:
            print("[ERREUR] Modification NON appliquee en memoire")
            return False
        
        # 5. Vérification par rechargement depuis la base
        print("\nETAPE 4 : Verification par rechargement depuis la base de donnees")
        eleve_recharge = Eleve.objects.get(id=eleve.id)
        print(f"   Statut rechargé depuis la DB : {eleve_recharge.statut}")
        
        if eleve_recharge.statut == nouveau_statut:
            print("[OK] Modification PERSISTEE dans la base de donnees")
        else:
            print("[ERREUR] Modification NON persistee dans la base de donnees")
            print(f"   Attendu : {nouveau_statut}")
            print(f"   Trouvé : {eleve_recharge.statut}")
            return False
        
        # 6. Test avec une nouvelle instance
        print("\nETAPE 5 : Verification avec nouvelle instance")
        nouvelle_instance = Eleve.objects.filter(id=eleve.id).first()
        print(f"   Statut nouvelle instance : {nouvelle_instance.statut}")
        
        if nouvelle_instance.statut == nouveau_statut:
            print("[OK] Modification confirmee avec nouvelle instance")
        else:
            print("[ERREUR] Modification NON confirmee avec nouvelle instance")
            return False
        
        # 7. Test de modification inverse pour confirmer
        print("\nETAPE 6 : Test de modification inverse")
        print(f"   Retour au statut original : {statut_original}")
        
        form_data['statut'] = statut_original
        form_retour = EleveForm(data=form_data, instance=nouvelle_instance)
        
        if form_retour.is_valid():
            eleve_restaure = form_retour.save()
            print(f"[OK] Statut restaure : {eleve_restaure.statut}")
            
            # Vérification finale
            verification_finale = Eleve.objects.get(id=eleve.id)
            if verification_finale.statut == statut_original:
                print("[OK] Restauration confirmee dans la base de donnees")
            else:
                print("[ERREUR] Restauration NON confirmee dans la base de donnees")
                return False
        else:
            print("[ERREUR] Erreur lors de la restauration")
            return False
        
        print("\n" + "=" * 80)
        print("RESULTAT FINAL : TOUTES LES VERIFICATIONS REUSSIES")
        print("[OK] Les modifications de statut sont correctement appliquees et persistees")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n[ERREUR] ERREUR lors du test : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_modification_via_vue():
    """
    Test de modification via la vue Django (simulation POST)
    """
    print("\n" + "=" * 80)
    print("TEST COMPLEMENTAIRE - MODIFICATION VIA VUE DJANGO")
    print("=" * 80)
    
    try:
        # Création d'un client de test
        client = Client()
        
        # Création d'un utilisateur de test
        user = User.objects.filter(username='test_user').first()
        if not user:
            user = User.objects.create_user(username='test_user', password='testpass')
        
        # Connexion
        client.login(username='test_user', password='testpass')
        
        # Récupération d'un élève
        eleve = Eleve.objects.first()
        if not eleve:
            print("[ERREUR] Aucun eleve disponible pour le test")
            return False
        
        print(f"Test avec eleve : {eleve.prenom} {eleve.nom}")
        print(f"   Statut actuel : {eleve.statut}")
        
        # Préparation des données POST
        statut_original = eleve.statut
        nouveau_statut = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        
        post_data = {
            'matricule': eleve.matricule,
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'statut': nouveau_statut,
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d'),
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d'),
            'classe': eleve.classe.id if eleve.classe else '',
            'responsable_principal': eleve.responsable_principal.id if eleve.responsable_principal else '',
            'responsable_secondaire': eleve.responsable_secondaire.id if eleve.responsable_secondaire else '',
        }
        
        # Envoi de la requête POST
        url = reverse('eleves:modifier_eleve', kwargs={'eleve_id': eleve.id})
        response = client.post(url, data=post_data)
        
        print(f"Requete POST envoyee vers : {url}")
        print(f"   Code de réponse : {response.status_code}")
        
        # Vérification de la redirection (succès)
        if response.status_code in [200, 302]:
            print("[OK] Requete traitee avec succes")
            
            # Vérification en base
            eleve_modifie = Eleve.objects.get(id=eleve.id)
            print(f"   Statut après modification via vue : {eleve_modifie.statut}")
            
            if eleve_modifie.statut == nouveau_statut:
                print("[OK] Modification via vue REUSSIE et persistee")
                
                # Restauration
                post_data['statut'] = statut_original
                client.post(url, data=post_data)
                
                eleve_restaure = Eleve.objects.get(id=eleve.id)
                if eleve_restaure.statut == statut_original:
                    print("[OK] Restauration via vue REUSSIE")
                    return True
                else:
                    print("[ERREUR] Restauration via vue ECHOUEE")
                    return False
            else:
                print("[ERREUR] Modification via vue ECHOUEE")
                print(f"   Attendu : {nouveau_statut}")
                print(f"   Trouvé : {eleve_modifie.statut}")
                return False
        else:
            print(f"[ERREUR] Erreur dans la requete : {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERREUR] Erreur lors du test via vue : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("LANCEMENT DES TESTS DE VERIFICATION DES MODIFICATIONS DE STATUT")
    
    # Test 1 : Modification directe via formulaire
    test1_result = test_modification_statut_persistence()
    
    # Test 2 : Modification via vue Django
    test2_result = test_modification_via_vue()
    
    print("\n" + "=" * 80)
    print("RESUME DES TESTS")
    print("=" * 80)
    print(f"Test 1 - Modification directe : {'[OK] REUSSI' if test1_result else '[ERREUR] ECHOUE'}")
    print(f"Test 2 - Modification via vue : {'[OK] REUSSI' if test2_result else '[ERREUR] ECHOUE'}")
    
    if test1_result and test2_result:
        print("\nCONCLUSION : LES MODIFICATIONS DE STATUT SONT CORRECTEMENT PERSISTEES")
        print("[OK] La base de donnees est mise a jour apres chaque modification")
    else:
        print("\nCONCLUSION : PROBLEME DETECTE DANS LA PERSISTANCE DES MODIFICATIONS")
        print("[ERREUR] Verification necessaire du code de sauvegarde")
    
    print("=" * 80)
