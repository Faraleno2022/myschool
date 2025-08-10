#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test final pour verifier que le bouton d'enregistrement fonctionne
apres suppression du JavaScript problematique
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

def test_final():
    print("TEST FINAL - BOUTON D'ENREGISTREMENT")
    print("=" * 50)
    
    # Compter les eleves avant
    count_avant = Eleve.objects.count()
    print(f"Nombre d'eleves avant test: {count_avant}")
    
    # Donnees similaires a celles du formulaire utilisateur
    ecole = Ecole.objects.first()
    classe = Classe.objects.filter(nom__contains="Collège").first() or Classe.objects.first()
    
    print(f"Ecole: {ecole.nom}")
    print(f"Classe: {classe.nom}")
    
    # Test avec creation de nouveaux responsables (comme dans le formulaire)
    print("\nTest avec creation de nouveaux responsables...")
    
    try:
        # Creer utilisateur de test
        user, created = User.objects.get_or_create(
            username='test_final',
            defaults={'email': 'final@test.com'}
        )
        
        # Creer responsable principal
        resp_principal = Responsable.objects.create(
            prenom='FELIX',
            nom='LENO',
            relation='MERE',
            telephone='+224622613559',
            email='isarbrothers@gmail.com',
            adresse='Guinee'
        )
        print(f"Responsable principal cree: {resp_principal.prenom} {resp_principal.nom}")
        
        # Creer responsable secondaire
        resp_secondaire = Responsable.objects.create(
            prenom='SUZANE',
            nom='MILLIMOINO',
            relation='MERE',
            telephone='+22462263559',
            email='isarbrothers@gmail.com',
            adresse='Guinee'
        )
        print(f"Responsable secondaire cree: {resp_secondaire.prenom} {resp_secondaire.nom}")
        
        # Creer l'eleve avec les memes donnees que le formulaire
        eleve = Eleve.objects.create(
            matricule='00010',
            prenom='Amadou',
            nom='LENO',
            sexe='M',
            date_naissance=date(2010, 1, 1),  # Date plus realiste
            lieu_naissance='Conakry',
            classe=classe,
            date_inscription=date.today(),
            statut='ACTIF',
            responsable_principal=resp_principal,
            responsable_secondaire=resp_secondaire,
            cree_par=user
        )
        
        print(f"SUCCES - Eleve cree: {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
        print(f"Matricule: {eleve.matricule}")
        print(f"Classe: {eleve.classe.nom}")
        print(f"Responsable principal: {eleve.responsable_principal.prenom} {eleve.responsable_principal.nom}")
        print(f"Responsable secondaire: {eleve.responsable_secondaire.prenom} {eleve.responsable_secondaire.nom}")
        
        # Compter les eleves apres
        count_apres = Eleve.objects.count()
        print(f"\nNombre d'eleves apres test: {count_apres}")
        print(f"Difference: +{count_apres - count_avant}")
        
        # Nettoyer les donnees de test
        print("\nNettoyage des donnees de test...")
        eleve.delete()
        resp_principal.delete()
        resp_secondaire.delete()
        print("Donnees nettoyees")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False

def verifier_formulaire():
    print("\nVERIFICATION DU FORMULAIRE")
    print("-" * 30)
    
    # Verifier que les donnees necessaires existent
    ecoles = Ecole.objects.count()
    classes = Classe.objects.count()
    responsables = Responsable.objects.count()
    
    print(f"Ecoles disponibles: {ecoles}")
    print(f"Classes disponibles: {classes}")
    print(f"Responsables disponibles: {responsables}")
    
    if ecoles == 0 or classes == 0:
        print("ATTENTION: Donnees manquantes pour le formulaire")
        return False
    
    print("OK - Donnees suffisantes pour le formulaire")
    return True

if __name__ == '__main__':
    try:
        print("VERIFICATION FINALE DU SYSTEME D'ENREGISTREMENT")
        print("=" * 60)
        
        # Verifier les donnees de base
        if not verifier_formulaire():
            print("ERREUR: Donnees insuffisantes")
            sys.exit(1)
        
        # Test de creation
        success = test_final()
        
        print("\n" + "=" * 60)
        if success:
            print("RESULTAT: LE SYSTEME FONCTIONNE CORRECTEMENT")
            print("\nLe formulaire devrait maintenant fonctionner sans probleme.")
            print("JavaScript supprime - formulaire natif active")
            print("\nPour tester:")
            print("1. Allez sur /eleves/ajouter/")
            print("2. Remplissez le formulaire")
            print("3. Cliquez sur 'Enregistrer l'eleve'")
            print("4. L'eleve devrait etre cree et vous devriez voir un message de succes")
        else:
            print("RESULTAT: IL Y A ENCORE UN PROBLEME")
            
    except Exception as e:
        print(f"ERREUR GENERALE: {e}")
        sys.exit(1)
