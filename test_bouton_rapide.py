#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test rapide pour verifier le bouton d'enregistrement
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
from eleves.forms import EleveForm

def test_rapide():
    print("TEST RAPIDE DU BOUTON D'ENREGISTREMENT")
    print("=" * 50)
    
    try:
        # Prendre les premiers elements disponibles
        ecole = Ecole.objects.first()
        classe = Classe.objects.first()
        responsable = Responsable.objects.first()
        
        if not all([ecole, classe, responsable]):
            print("ERREUR: Donnees manquantes (ecole, classe ou responsable)")
            return False
        
        print(f"Ecole: {ecole.nom}")
        print(f"Classe: {classe.nom}")
        print(f"Responsable: {responsable.prenom} {responsable.nom}")
        
        # Donnees de test
        donnees = {
            'matricule': 'TESTRAPIDE001',
            'prenom': 'Test',
            'nom': 'Rapide',
            'sexe': 'M',
            'date_naissance': date(2015, 1, 1),
            'lieu_naissance': 'Conakry',
            'classe': classe.id,
            'date_inscription': date.today(),
            'statut': 'ACTIF',
            'responsable_principal': responsable.id,
        }
        
        # Test du formulaire
        form = EleveForm(data=donnees)
        
        if form.is_valid():
            print("OK - Formulaire valide")
            
            # Creer utilisateur de test
            user, created = User.objects.get_or_create(
                username='test_rapide',
                defaults={'email': 'test@rapide.com'}
            )
            
            # Sauvegarder
            eleve = form.save(commit=False)
            eleve.cree_par = user
            eleve.save()
            
            print(f"SUCCES - Eleve cree: {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
            
            # Nettoyer
            eleve.delete()
            print("OK - Donnees de test nettoyees")
            
            return True
        else:
            print("ERREUR - Formulaire invalide:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors[0]}")
            return False
            
    except Exception as e:
        print(f"ERREUR: {e}")
        return False

if __name__ == '__main__':
    success = test_rapide()
    if success:
        print("\nCONCLUSION: Le bouton d'enregistrement devrait fonctionner!")
        print("Testez maintenant sur /eleves/ajouter/")
    else:
        print("\nPROBLEME: Il y a encore des erreurs a corriger")
