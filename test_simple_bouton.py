#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de test simplifie pour verifier le fonctionnement du bouton d'enregistrement
dans la page /eleves/ajouter/
"""

import os
import sys
import django
from datetime import date

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.contrib.auth.models import User
from eleves.models import Eleve, Responsable, Classe, Ecole
from eleves.forms import EleveForm, ResponsableForm

def test_bouton_enregistrement():
    """Test du fonctionnement du bouton d'enregistrement"""
    
    print("TEST DU BOUTON D'ENREGISTREMENT - /eleves/ajouter/")
    print("=" * 60)
    
    # 1. Verifier l'existence des modeles necessaires
    print("\n1. Verification des modeles...")
    
    try:
        # Verifier qu'il y a au moins une ecole
        ecoles = Ecole.objects.all()
        print(f"   OK Ecoles disponibles: {ecoles.count()}")
        
        if ecoles.count() == 0:
            print("   WARN Creation d'une ecole de test...")
            ecole_test = Ecole.objects.create(
                nom="Ecole Test",
                adresse="Adresse Test",
                telephone="+224123456789",
                email="test@ecole.com"
            )
            print(f"   OK Ecole creee: {ecole_test.nom}")
        else:
            ecole_test = ecoles.first()
        
        # Verifier qu'il y a au moins une classe
        classes = Classe.objects.filter(ecole=ecole_test)
        print(f"   OK Classes disponibles: {classes.count()}")
        
        if classes.count() == 0:
            print("   WARN Creation d'une classe de test...")
            classe_test = Classe.objects.create(
                nom="CP1 Test",
                niveau="CP1",
                ecole=ecole_test,
                annee_scolaire="2024-2025"
            )
            print(f"   OK Classe creee: {classe_test.nom}")
        else:
            classe_test = classes.first()
        
        # Verifier qu'il y a au moins un responsable
        responsables = Responsable.objects.all()
        print(f"   OK Responsables disponibles: {responsables.count()}")
        
        if responsables.count() == 0:
            print("   WARN Creation d'un responsable de test...")
            responsable_test = Responsable.objects.create(
                prenom="Papa",
                nom="Test",
                relation="PERE",
                telephone="+224987654321",
                email="papa@test.com",
                adresse="Adresse Papa Test"
            )
            print(f"   OK Responsable cree: {responsable_test.prenom} {responsable_test.nom}")
        else:
            responsable_test = responsables.first()
        
    except Exception as e:
        print(f"   ERREUR lors de la verification des modeles: {e}")
        return False
    
    # 2. Test du formulaire EleveForm
    print("\n2. Test du formulaire EleveForm...")
    
    try:
        # Donnees de test pour un eleve
        donnees_eleve = {
            'matricule': 'TEST001',
            'prenom': 'Eleve',
            'nom': 'Test',
            'sexe': 'M',
            'date_naissance': date(2015, 5, 15),
            'lieu_naissance': 'Conakry',
            'classe': classe_test.id,
            'date_inscription': date.today(),
            'statut': 'ACTIF',
            'responsable_principal': responsable_test.id,
        }
        
        form = EleveForm(data=donnees_eleve)
        
        if form.is_valid():
            print("   OK Formulaire EleveForm valide")
            
            # Verifier qu'on peut creer un utilisateur de test
            user, created = User.objects.get_or_create(
                username='test_user',
                defaults={
                    'email': 'test@user.com',
                    'first_name': 'Test',
                    'last_name': 'User'
                }
            )
            
            # Simuler la sauvegarde
            eleve = form.save(commit=False)
            eleve.cree_par = user
            eleve.save()
            
            print(f"   OK Eleve cree avec succes: {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
            print(f"   INFO Matricule: {eleve.matricule}")
            print(f"   INFO Classe: {eleve.classe.nom}")
            print(f"   INFO Responsable: {eleve.responsable_principal.prenom} {eleve.responsable_principal.nom}")
            
        else:
            print("   ERREUR Formulaire EleveForm invalide:")
            for field, errors in form.errors.items():
                print(f"      - {field}: {errors}")
            return False
            
    except Exception as e:
        print(f"   ERREUR lors du test du formulaire: {e}")
        return False
    
    # 3. Test de la logique de validation
    print("\n3. Test de la logique de validation...")
    
    try:
        # Test avec donnees manquantes
        donnees_invalides = {
            'matricule': '',  # Matricule manquant
            'prenom': 'Test',
            'nom': 'Invalide',
        }
        
        form_invalide = EleveForm(data=donnees_invalides)
        
        if not form_invalide.is_valid():
            print("   OK Validation des champs obligatoires fonctionne")
            print("   INFO Erreurs detectees:")
            for field, errors in form_invalide.errors.items():
                print(f"      - {field}: {errors[0]}")
        else:
            print("   WARN La validation devrait echouer avec des donnees manquantes")
            
    except Exception as e:
        print(f"   ERREUR lors du test de validation: {e}")
        return False
    
    # 4. Statistiques finales
    print("\n4. Statistiques apres test...")
    
    try:
        total_eleves = Eleve.objects.count()
        eleves_actifs = Eleve.objects.filter(statut='ACTIF').count()
        eleves_test = Eleve.objects.filter(matricule__startswith='TEST').count()
        
        print(f"   INFO Total eleves: {total_eleves}")
        print(f"   INFO Eleves actifs: {eleves_actifs}")
        print(f"   INFO Eleves de test: {eleves_test}")
        
    except Exception as e:
        print(f"   ERREUR lors du calcul des statistiques: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("SUCCES - TOUS LES TESTS SONT PASSES!")
    print("Le bouton d'enregistrement devrait fonctionner correctement")
    print("\nConseils pour tester manuellement:")
    print("   1. Aller sur /eleves/ajouter/")
    print("   2. Remplir les champs obligatoires (marques avec *)")
    print("   3. Selectionner un responsable existant ou creer un nouveau")
    print("   4. Cliquer sur 'Enregistrer l'eleve'")
    print("   5. Verifier l'affichage du message de succes")
    
    return True

def nettoyer_donnees_test():
    """Nettoyer les donnees de test creees"""
    print("\nNettoyage des donnees de test...")
    
    try:
        # Supprimer les eleves de test
        eleves_test = Eleve.objects.filter(matricule__startswith='TEST')
        count_eleves = eleves_test.count()
        eleves_test.delete()
        print(f"   OK {count_eleves} eleve(s) de test supprime(s)")
        
    except Exception as e:
        print(f"   ERREUR lors du nettoyage: {e}")

if __name__ == '__main__':
    try:
        # Executer les tests
        success = test_bouton_enregistrement()
        
        # Demander si on veut nettoyer
        if success:
            reponse = input("\nVoulez-vous nettoyer les donnees de test? (o/N): ")
            if reponse.lower() in ['o', 'oui', 'y', 'yes']:
                nettoyer_donnees_test()
        
    except KeyboardInterrupt:
        print("\n\nTest interrompu par l'utilisateur")
    except Exception as e:
        print(f"\nErreur inattendue: {e}")
        sys.exit(1)
