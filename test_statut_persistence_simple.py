#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test simple pour vérifier que les modifications de statut sont bien persistées en base de données
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve

def test_modification_statut_direct():
    """
    Test direct de modification de statut via l'ORM Django
    """
    print("=" * 80)
    print("TEST DIRECT - PERSISTANCE DES MODIFICATIONS DE STATUT")
    print("=" * 80)
    
    try:
        # 1. Récupération d'un élève existant
        print("\nETAPE 1 : Recuperation d'un eleve existant")
        eleve = Eleve.objects.first()
        if not eleve:
            print("[ERREUR] Aucun eleve trouve dans la base de donnees")
            return False
            
        print(f"[OK] Eleve trouve : {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
        print(f"   Statut actuel : {eleve.statut}")
        
        # 2. Sauvegarde du statut original
        statut_original = eleve.statut
        print(f"   Statut original sauvegarde : {statut_original}")
        
        # 3. Modification directe du statut
        print("\nETAPE 2 : Modification directe du statut")
        nouveau_statut = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        print(f"   Nouveau statut a appliquer : {nouveau_statut}")
        
        # Modification directe via l'ORM
        eleve.statut = nouveau_statut
        eleve.save()
        print(f"[OK] Statut modifie et sauvegarde : {eleve.statut}")
        
        # 4. Vérification immédiate en mémoire
        print("\nETAPE 3 : Verification immediate (objet en memoire)")
        print(f"   Statut de l'objet modifie : {eleve.statut}")
        
        if eleve.statut == nouveau_statut:
            print("[OK] Modification appliquee en memoire")
        else:
            print("[ERREUR] Modification NON appliquee en memoire")
            return False
        
        # 5. Vérification par rechargement depuis la base
        print("\nETAPE 4 : Verification par rechargement depuis la base de donnees")
        eleve_recharge = Eleve.objects.get(id=eleve.id)
        print(f"   Statut recharge depuis la DB : {eleve_recharge.statut}")
        
        if eleve_recharge.statut == nouveau_statut:
            print("[OK] Modification PERSISTEE dans la base de donnees")
        else:
            print("[ERREUR] Modification NON persistee dans la base de donnees")
            print(f"   Attendu : {nouveau_statut}")
            print(f"   Trouve : {eleve_recharge.statut}")
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
        
        nouvelle_instance.statut = statut_original
        nouvelle_instance.save()
        print(f"[OK] Statut restaure : {nouvelle_instance.statut}")
        
        # Vérification finale
        verification_finale = Eleve.objects.get(id=eleve.id)
        if verification_finale.statut == statut_original:
            print("[OK] Restauration confirmee dans la base de donnees")
        else:
            print("[ERREUR] Restauration NON confirmee dans la base de donnees")
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

def test_modification_avec_update():
    """
    Test de modification avec la méthode update() de Django
    """
    print("\n" + "=" * 80)
    print("TEST AVEC UPDATE() - MODIFICATION EN LOT")
    print("=" * 80)
    
    try:
        # Récupération d'un élève
        eleve = Eleve.objects.first()
        if not eleve:
            print("[ERREUR] Aucun eleve disponible pour le test")
            return False
        
        print(f"Test avec eleve : {eleve.prenom} {eleve.nom}")
        statut_original = eleve.statut
        print(f"   Statut actuel : {statut_original}")
        
        # Modification avec update()
        nouveau_statut = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        print(f"   Nouveau statut : {nouveau_statut}")
        
        # Utilisation de update() pour modifier directement en base
        nb_modifies = Eleve.objects.filter(id=eleve.id).update(statut=nouveau_statut)
        print(f"[OK] Nombre d'eleves modifies avec update() : {nb_modifies}")
        
        # Vérification
        eleve_verifie = Eleve.objects.get(id=eleve.id)
        if eleve_verifie.statut == nouveau_statut:
            print("[OK] Modification avec update() REUSSIE et persistee")
            
            # Restauration
            Eleve.objects.filter(id=eleve.id).update(statut=statut_original)
            eleve_restaure = Eleve.objects.get(id=eleve.id)
            
            if eleve_restaure.statut == statut_original:
                print("[OK] Restauration avec update() REUSSIE")
                return True
            else:
                print("[ERREUR] Restauration avec update() ECHOUEE")
                return False
        else:
            print("[ERREUR] Modification avec update() ECHOUEE")
            print(f"   Attendu : {nouveau_statut}")
            print(f"   Trouve : {eleve_verifie.statut}")
            return False
            
    except Exception as e:
        print(f"[ERREUR] Erreur lors du test avec update() : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_verification_complete_statuts():
    """
    Vérification complète de tous les statuts possibles
    """
    print("\n" + "=" * 80)
    print("TEST COMPLET - VERIFICATION DE TOUS LES STATUTS")
    print("=" * 80)
    
    try:
        eleve = Eleve.objects.first()
        if not eleve:
            print("[ERREUR] Aucun eleve disponible")
            return False
        
        statut_original = eleve.statut
        print(f"Eleve de test : {eleve.prenom} {eleve.nom}")
        print(f"Statut original : {statut_original}")
        
        # Liste des statuts à tester
        statuts_a_tester = ['ACTIF', 'SUSPENDU', 'TRANSFERE', 'DIPLOME']
        
        for statut_test in statuts_a_tester:
            if statut_test == statut_original:
                continue  # Skip le statut actuel
                
            print(f"\n--- Test du statut : {statut_test} ---")
            
            # Modification
            eleve.statut = statut_test
            eleve.save()
            
            # Vérification immédiate
            if eleve.statut == statut_test:
                print(f"[OK] Statut {statut_test} applique en memoire")
            else:
                print(f"[ERREUR] Statut {statut_test} NON applique en memoire")
                return False
            
            # Vérification en base
            eleve_db = Eleve.objects.get(id=eleve.id)
            if eleve_db.statut == statut_test:
                print(f"[OK] Statut {statut_test} persiste en base")
            else:
                print(f"[ERREUR] Statut {statut_test} NON persiste en base")
                return False
        
        # Restauration du statut original
        eleve.statut = statut_original
        eleve.save()
        
        verification_finale = Eleve.objects.get(id=eleve.id)
        if verification_finale.statut == statut_original:
            print(f"\n[OK] Statut original {statut_original} restaure avec succes")
            return True
        else:
            print(f"\n[ERREUR] Echec de la restauration du statut original")
            return False
            
    except Exception as e:
        print(f"[ERREUR] Erreur lors du test complet : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("LANCEMENT DES TESTS DE VERIFICATION DES MODIFICATIONS DE STATUT")
    
    # Test 1 : Modification directe
    test1_result = test_modification_statut_direct()
    
    # Test 2 : Modification avec update()
    test2_result = test_modification_avec_update()
    
    # Test 3 : Vérification complète de tous les statuts
    test3_result = test_verification_complete_statuts()
    
    print("\n" + "=" * 80)
    print("RESUME DES TESTS")
    print("=" * 80)
    print(f"Test 1 - Modification directe : {'[OK] REUSSI' if test1_result else '[ERREUR] ECHOUE'}")
    print(f"Test 2 - Modification avec update() : {'[OK] REUSSI' if test2_result else '[ERREUR] ECHOUE'}")
    print(f"Test 3 - Test complet statuts : {'[OK] REUSSI' if test3_result else '[ERREUR] ECHOUE'}")
    
    if test1_result and test2_result and test3_result:
        print("\nCONCLUSION : LES MODIFICATIONS DE STATUT SONT CORRECTEMENT PERSISTEES")
        print("[OK] La base de donnees est mise a jour apres chaque modification")
        print("[OK] Tous les statuts peuvent etre modifies et persistes")
        print("[OK] Les methodes save() et update() fonctionnent correctement")
    else:
        print("\nCONCLUSION : PROBLEME DETECTE DANS LA PERSISTANCE DES MODIFICATIONS")
        print("[ERREUR] Verification necessaire du code de sauvegarde")
    
    print("=" * 80)
