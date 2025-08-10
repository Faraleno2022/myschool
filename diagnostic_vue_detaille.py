#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnostic détaillé de la vue ajouter_eleve pour identifier le problème exact
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

def diagnostic_complet():
    print("DIAGNOSTIC DÉTAILLÉ - VUE AJOUTER_ELEVE")
    print("=" * 60)
    
    # Données de test
    ecole = Ecole.objects.first()
    classe = Classe.objects.first()
    
    print(f"Ecole: {ecole.nom}")
    print(f"Classe: {classe.nom}")
    
    # Données POST simulant la soumission du formulaire
    import random
    matricule_unique = f'DIAG{random.randint(100, 999)}'
    
    donnees_post = {
        # Données élève
        'matricule': matricule_unique,
        'prenom': 'Test',
        'nom': 'Diagnostic',
        'sexe': 'M',
        'date_naissance': '2015-01-01',
        'lieu_naissance': 'Conakry',
        'classe': str(classe.id),
        'date_inscription': date.today().strftime('%Y-%m-%d'),
        'statut': 'ACTIF',
        
        # Indiquer qu'on crée un nouveau responsable
        'responsable_principal_nouveau': 'on',
        
        # Données du nouveau responsable (avec prefix)
        'resp_principal-prenom': 'Papa',
        'resp_principal-nom': 'Diagnostic',
        'resp_principal-relation': 'PERE',
        'resp_principal-telephone': '+224123456789',
        'resp_principal-email': 'papa.diagnostic@test.com',
        'resp_principal-adresse': 'Adresse Papa Diagnostic',
        'resp_principal-profession': 'Ingenieur',
        
        # Pas de responsable secondaire
        'responsable_secondaire_nouveau': '',
    }
    
    print(f"\nMatricule unique: {matricule_unique}")
    print("Données POST préparées")
    
    try:
        # Étape 1: Test du formulaire EleveForm
        print("\n" + "-" * 40)
        print("ÉTAPE 1: Test EleveForm")
        print("-" * 40)
        
        form = EleveForm(donnees_post)
        print(f"EleveForm.is_valid(): {form.is_valid()}")
        
        if not form.is_valid():
            print("Erreurs EleveForm:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
        else:
            print("✅ EleveForm valide")
        
        # Étape 2: Test du formulaire ResponsableForm
        print("\n" + "-" * 40)
        print("ÉTAPE 2: Test ResponsableForm")
        print("-" * 40)
        
        responsable_form = ResponsableForm(donnees_post, prefix='resp_principal')
        print(f"ResponsableForm.is_valid(): {responsable_form.is_valid()}")
        
        if not responsable_form.is_valid():
            print("Erreurs ResponsableForm:")
            for field, errors in responsable_form.errors.items():
                print(f"  {field}: {errors}")
        else:
            print("✅ ResponsableForm valide")
            print("Données nettoyées du responsable:")
            for field, value in responsable_form.cleaned_data.items():
                print(f"  {field}: {value}")
        
        # Étape 3: Simulation de la logique de la vue
        print("\n" + "-" * 40)
        print("ÉTAPE 3: Simulation logique vue")
        print("-" * 40)
        
        # Variables de la vue
        creer_resp_principal = donnees_post.get('responsable_principal_nouveau') == 'on'
        print(f"creer_resp_principal: {creer_resp_principal}")
        
        form_valide = form.is_valid()
        resp_principal_valide = responsable_form.is_valid() if creer_resp_principal else True
        
        print(f"form_valide: {form_valide}")
        print(f"resp_principal_valide: {resp_principal_valide}")
        
        # Vérification responsable principal
        responsable_principal_fourni = True
        if form_valide:
            if not creer_resp_principal and not form.cleaned_data.get('responsable_principal'):
                print("❌ Aucun responsable principal fourni")
                responsable_principal_fourni = False
            else:
                print("✅ Responsable principal fourni")
        
        # Condition finale
        condition_finale = form_valide and resp_principal_valide and responsable_principal_fourni
        print(f"Condition finale (tous validés): {condition_finale}")
        
        # Étape 4: Test de création si tout est valide
        if condition_finale:
            print("\n" + "-" * 40)
            print("ÉTAPE 4: Test de création")
            print("-" * 40)
            
            try:
                # Créer le responsable
                if creer_resp_principal:
                    print("Création du responsable...")
                    responsable_principal = responsable_form.save()
                    print(f"✅ Responsable créé: {responsable_principal.prenom} {responsable_principal.nom}")
                    
                    # Assigner à l'élève
                    form.instance.responsable_principal = responsable_principal
                
                # Créer l'élève
                print("Création de l'élève...")
                user = User.objects.get_or_create(username='test_diagnostic')[0]
                eleve = form.save(commit=False)
                eleve.cree_par = user
                eleve.save()
                
                print(f"✅ Élève créé: {eleve.prenom} {eleve.nom}")
                print(f"✅ Responsable assigné: {eleve.responsable_principal.prenom} {eleve.responsable_principal.nom}")
                
                # Nettoyer
                eleve.delete()
                responsable_principal.delete()
                print("✅ Données de test nettoyées")
                
                return True
                
            except Exception as e:
                print(f"❌ Erreur lors de la création: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print("\n❌ Conditions non remplies pour la création")
            return False
            
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validation_manuelle():
    print("\n" + "=" * 60)
    print("TEST VALIDATION MANUELLE DES CHAMPS RESPONSABLE")
    print("=" * 60)
    
    # Test avec données complètes
    donnees_completes = {
        'resp_principal-prenom': 'Papa',
        'resp_principal-nom': 'Test',
        'resp_principal-relation': 'PERE',
        'resp_principal-telephone': '+224123456789',
        'resp_principal-email': 'papa@test.com',
        'resp_principal-adresse': 'Adresse Papa',
        'resp_principal-profession': 'Ingenieur'
    }
    
    print("Test avec données complètes:")
    form_complet = ResponsableForm(donnees_completes, prefix='resp_principal')
    print(f"is_valid(): {form_complet.is_valid()}")
    
    if not form_complet.is_valid():
        print("Erreurs:")
        for field, errors in form_complet.errors.items():
            print(f"  {field}: {errors}")
    else:
        print("✅ Formulaire valide avec données complètes")
    
    # Test avec données partielles
    donnees_partielles = {
        'resp_principal-prenom': 'Papa',
        'resp_principal-nom': 'Test',
        'resp_principal-relation': 'PERE',
        'resp_principal-telephone': '+224123456789',
        # Pas d'email, adresse, profession
    }
    
    print("\nTest avec données partielles (sans email, adresse, profession):")
    form_partiel = ResponsableForm(donnees_partielles, prefix='resp_principal')
    print(f"is_valid(): {form_partiel.is_valid()}")
    
    if not form_partiel.is_valid():
        print("Erreurs:")
        for field, errors in form_partiel.errors.items():
            print(f"  {field}: {errors}")
    else:
        print("✅ Formulaire valide avec données partielles")
    
    # Test avec données minimales
    donnees_minimales = {
        'resp_principal-prenom': 'Papa',
        'resp_principal-nom': 'Test',
        'resp_principal-relation': 'PERE',
        # Pas de téléphone, email, adresse, profession
    }
    
    print("\nTest avec données minimales (prenom, nom, relation seulement):")
    form_minimal = ResponsableForm(donnees_minimales, prefix='resp_principal')
    print(f"is_valid(): {form_minimal.is_valid()}")
    
    if not form_minimal.is_valid():
        print("Erreurs:")
        for field, errors in form_partiel.errors.items():
            print(f"  {field}: {errors}")
    else:
        print("✅ Formulaire valide avec données minimales")

if __name__ == '__main__':
    try:
        success = diagnostic_complet()
        test_validation_manuelle()
        
        print("\n" + "=" * 60)
        if success:
            print("✅ DIAGNOSTIC RÉUSSI - La logique fonctionne correctement")
        else:
            print("❌ DIAGNOSTIC ÉCHOUÉ - Problème identifié")
            
    except Exception as e:
        print(f"ERREUR GÉNÉRALE: {e}")
        sys.exit(1)
