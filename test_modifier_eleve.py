#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test pour vérifier que la modification d'élève fonctionne correctement
après les changements apportés aux formulaires
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
from eleves.forms import EleveForm
from eleves.views import modifier_eleve

def test_modification_eleve():
    print("TEST MODIFICATION D'ÉLÈVE")
    print("=" * 50)
    
    # Trouver un élève existant pour le test
    eleve_test = Eleve.objects.first()
    if not eleve_test:
        print("❌ Aucun élève trouvé pour le test")
        return False
    
    print(f"Élève de test: {eleve_test.prenom} {eleve_test.nom} (ID: {eleve_test.id})")
    print(f"Responsable actuel: {eleve_test.responsable_principal.prenom} {eleve_test.responsable_principal.nom}")
    
    # Sauvegarder les valeurs originales
    prenom_original = eleve_test.prenom
    lieu_original = eleve_test.lieu_naissance
    responsable_original = eleve_test.responsable_principal
    
    try:
        # Test 1: Modification simple des informations de l'élève
        print("\n" + "-" * 40)
        print("TEST 1: Modification informations élève")
        print("-" * 40)
        
        donnees_modification = {
            'matricule': eleve_test.matricule,
            'prenom': 'PrenomModifie',  # Changement
            'nom': eleve_test.nom,
            'sexe': eleve_test.sexe,
            'date_naissance': eleve_test.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': 'LieuModifie',  # Changement
            'classe': str(eleve_test.classe.id),
            'date_inscription': eleve_test.date_inscription.strftime('%Y-%m-%d'),
            'statut': eleve_test.statut,
            'responsable_principal': str(eleve_test.responsable_principal.id),
            'responsable_secondaire': str(eleve_test.responsable_secondaire.id) if eleve_test.responsable_secondaire else '',
        }
        
        print("Données de modification préparées")
        
        # Test du formulaire
        form = EleveForm(data=donnees_modification, instance=eleve_test)
        print(f"Formulaire valide: {form.is_valid()}")
        
        if not form.is_valid():
            print("Erreurs du formulaire:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
            return False
        
        # Sauvegarder les modifications
        eleve_modifie = form.save()
        print(f"✅ Élève modifié avec succès")
        print(f"Nouveau prénom: {eleve_modifie.prenom}")
        print(f"Nouveau lieu: {eleve_modifie.lieu_naissance}")
        
        # Test 2: Test de la vue modifier_eleve
        print("\n" + "-" * 40)
        print("TEST 2: Vue modifier_eleve")
        print("-" * 40)
        
        # Créer utilisateur de test
        user, created = User.objects.get_or_create(
            username='test_modifier',
            defaults={'email': 'test@modifier.com'}
        )
        
        # Préparer nouvelles données
        nouvelles_donnees = donnees_modification.copy()
        nouvelles_donnees['prenom'] = 'PrenomVueTest'
        nouvelles_donnees['lieu_naissance'] = 'LieuVueTest'
        
        # Créer requête POST
        factory = RequestFactory()
        request = factory.post(f'/eleves/{eleve_test.id}/modifier/', data=nouvelles_donnees)
        request.user = user
        
        # Ajouter sessions et messages
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        messages = FallbackStorage(request)
        request._messages = messages
        
        print("Appel de la vue modifier_eleve...")
        response = modifier_eleve(request, eleve_test.id)
        
        # Vérifier le résultat
        eleve_test.refresh_from_db()
        
        if eleve_test.prenom == 'PrenomVueTest' and eleve_test.lieu_naissance == 'LieuVueTest':
            print("✅ Vue modifier_eleve fonctionne correctement")
            print(f"Prénom mis à jour: {eleve_test.prenom}")
            print(f"Lieu mis à jour: {eleve_test.lieu_naissance}")
            success = True
        else:
            print("❌ Vue modifier_eleve n'a pas mis à jour les données")
            success = False
        
        # Test 3: Changement de responsable
        print("\n" + "-" * 40)
        print("TEST 3: Changement de responsable")
        print("-" * 40)
        
        # Trouver un autre responsable
        autre_responsable = Responsable.objects.exclude(id=responsable_original.id).first()
        if autre_responsable:
            donnees_responsable = nouvelles_donnees.copy()
            donnees_responsable['responsable_principal'] = str(autre_responsable.id)
            
            form_resp = EleveForm(data=donnees_responsable, instance=eleve_test)
            if form_resp.is_valid():
                eleve_resp = form_resp.save()
                print(f"✅ Responsable changé: {eleve_resp.responsable_principal.prenom} {eleve_resp.responsable_principal.nom}")
            else:
                print("❌ Erreur lors du changement de responsable")
                for field, errors in form_resp.errors.items():
                    print(f"  {field}: {errors}")
        else:
            print("⚠️ Pas d'autre responsable disponible pour le test")
        
        return success
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restaurer les valeurs originales
        print("\n" + "-" * 40)
        print("RESTAURATION DES DONNÉES ORIGINALES")
        print("-" * 40)
        
        try:
            eleve_test.prenom = prenom_original
            eleve_test.lieu_naissance = lieu_original
            eleve_test.responsable_principal = responsable_original
            eleve_test.save()
            print("✅ Données originales restaurées")
        except Exception as e:
            print(f"❌ Erreur lors de la restauration: {e}")

def test_formulaire_eleve_seul():
    print("\n" + "=" * 50)
    print("TEST FORMULAIRE ELEVE SEUL")
    print("=" * 50)
    
    # Test avec un élève existant
    eleve = Eleve.objects.first()
    if not eleve:
        print("❌ Aucun élève pour le test")
        return False
    
    print(f"Test avec élève: {eleve.prenom} {eleve.nom}")
    
    # Test 1: Formulaire en mode modification (avec instance)
    print("\nTest 1: Formulaire avec instance (modification)")
    form_modif = EleveForm(instance=eleve)
    
    print(f"Champ responsable_principal.required: {form_modif.fields['responsable_principal'].required}")
    print(f"Champ responsable_secondaire.required: {form_modif.fields['responsable_secondaire'].required}")
    
    # Test 2: Formulaire en mode création (sans instance)
    print("\nTest 2: Formulaire sans instance (création)")
    form_creation = EleveForm()
    
    print(f"Champ responsable_principal.required: {form_creation.fields['responsable_principal'].required}")
    print(f"Champ responsable_secondaire.required: {form_creation.fields['responsable_secondaire'].required}")
    
    # Test 3: Validation avec données partielles
    print("\nTest 3: Validation avec responsable vide")
    donnees_partielles = {
        'matricule': 'TEST_MODIF',
        'prenom': 'Test',
        'nom': 'Modification',
        'sexe': 'M',
        'date_naissance': '2015-01-01',
        'lieu_naissance': 'Test',
        'classe': str(eleve.classe.id),
        'date_inscription': date.today().strftime('%Y-%m-%d'),
        'statut': 'ACTIF',
        'responsable_principal': '',  # Vide
        'responsable_secondaire': '',  # Vide
    }
    
    form_partiel = EleveForm(data=donnees_partielles)
    print(f"Formulaire avec responsables vides valide: {form_partiel.is_valid()}")
    
    if not form_partiel.is_valid():
        print("Erreurs:")
        for field, errors in form_partiel.errors.items():
            print(f"  {field}: {errors}")
    
    return True

if __name__ == '__main__':
    try:
        print("TEST COMPLET - MODIFICATION D'ÉLÈVE")
        print("=" * 60)
        
        # Test du formulaire seul
        success1 = test_formulaire_eleve_seul()
        
        # Test de la modification complète
        success2 = test_modification_eleve()
        
        print("\n" + "=" * 60)
        if success1 and success2:
            print("✅ TOUS LES TESTS RÉUSSIS")
            print("La modification d'élève fonctionne correctement")
        else:
            print("❌ PROBLÈMES DÉTECTÉS")
            if not success1:
                print("- Problème avec le formulaire EleveForm")
            if not success2:
                print("- Problème avec la vue modifier_eleve")
                
    except Exception as e:
        print(f"ERREUR GÉNÉRALE: {e}")
        sys.exit(1)
