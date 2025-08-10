#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test pour vérifier que la correction du format de date de naissance fonctionne
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve
from eleves.forms import EleveForm

def test_correction_format_date():
    """
    Test pour vérifier que la date de naissance est maintenant correctement formatée
    """
    print("=" * 80)
    print("TEST CORRECTION - FORMAT DATE DE NAISSANCE")
    print("=" * 80)
    
    try:
        # 1. Récupération d'un élève avec date de naissance
        print("\nETAPE 1 : Recuperation d'un eleve avec date de naissance")
        eleve = Eleve.objects.first()
        if not eleve:
            print("[ERREUR] Aucun eleve trouve")
            return False
            
        print(f"[OK] Eleve trouve : {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
        print(f"   Date de naissance en base : {eleve.date_naissance}")
        
        # 2. Test du formulaire avec instance (après correction)
        print("\nETAPE 2 : Test du formulaire avec instance (apres correction)")
        form = EleveForm(instance=eleve)
        
        # 3. Vérification du rendu HTML du champ date
        print("\nETAPE 3 : Verification du rendu HTML du champ date")
        
        html_field = form['date_naissance']
        html_str = str(html_field)
        print(f"HTML du champ : {html_str}")
        
        # Recherche de la valeur dans le HTML
        import re
        value_match = re.search(r'value="([^"]*)"', html_str)
        if value_match:
            html_value = value_match.group(1)
            print(f"   Valeur dans le HTML : '{html_value}'")
            
            # Vérification du format ISO (YYYY-MM-DD)
            if re.match(r'^\d{4}-\d{2}-\d{2}$', html_value):
                print("[OK] Format ISO (YYYY-MM-DD) detecte dans le HTML")
                
                # Vérification que la date correspond
                date_attendue = eleve.date_naissance.strftime('%Y-%m-%d')
                if html_value == date_attendue:
                    print(f"[OK] La date HTML correspond a la date en base : {date_attendue}")
                else:
                    print(f"[ERREUR] Mismatch - Attendu: {date_attendue}, Trouve: {html_value}")
                    return False
            else:
                print(f"[ERREUR] Format non-ISO detecte : {html_value}")
                print("   Format attendu : YYYY-MM-DD")
                return False
        else:
            print("[ERREUR] Aucune valeur trouvee dans l'attribut value")
            return False
        
        # 4. Test de soumission du formulaire
        print("\nETAPE 4 : Test de soumission du formulaire")
        
        post_data = {
            'matricule': eleve.matricule,
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'statut': eleve.statut,
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d'),
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d') if eleve.date_inscription else '',
            'lieu_naissance': eleve.lieu_naissance or '',
            'classe': eleve.classe.id if eleve.classe else '',
            'responsable_principal': eleve.responsable_principal.id if eleve.responsable_principal else '',
            'responsable_secondaire': eleve.responsable_secondaire.id if eleve.responsable_secondaire else '',
        }
        
        form_post = EleveForm(data=post_data, instance=eleve)
        
        if form_post.is_valid():
            print("[OK] Formulaire avec format ISO valide")
            
            # Vérification de la date dans les données nettoyées
            cleaned_date = form_post.cleaned_data.get('date_naissance')
            print(f"   Date nettoyee : {cleaned_date}")
            
            if cleaned_date == eleve.date_naissance:
                print("[OK] Date nettoyee correspond a la date originale")
            else:
                print(f"[ERREUR] Mismatch date nettoyee - Original: {eleve.date_naissance}, Nettoyee: {cleaned_date}")
                return False
        else:
            print("[ERREUR] Formulaire avec format ISO invalide :")
            for field, errors in form_post.errors.items():
                print(f"   {field}: {errors}")
            return False
        
        # 5. Test avec différentes dates
        print("\nETAPE 5 : Test avec differentes dates")
        
        test_dates = ['2010-01-15', '2005-12-31', '2015-06-20']
        
        for test_date_str in test_dates:
            print(f"   Test avec date : {test_date_str}")
            
            test_data = post_data.copy()
            test_data['date_naissance'] = test_date_str
            
            test_form = EleveForm(data=test_data, instance=eleve)
            
            if test_form.is_valid():
                test_cleaned_date = test_form.cleaned_data.get('date_naissance')
                print(f"     [OK] Date {test_date_str} validee -> {test_cleaned_date}")
            else:
                print(f"     [ERREUR] Date {test_date_str} invalide : {test_form.errors.get('date_naissance', 'Erreur inconnue')}")
                return False
        
        print("\n" + "=" * 80)
        print("RESULTAT FINAL : CORRECTION DU FORMAT DE DATE REUSSIE")
        print("[OK] Les dates sont maintenant au format ISO (YYYY-MM-DD)")
        print("[OK] Le formulaire affiche et accepte correctement les dates")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n[ERREUR] Erreur lors du test : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_widget_date_inscription():
    """
    Test pour vérifier que la date d'inscription utilise aussi le bon format
    """
    print("\n" + "=" * 80)
    print("TEST CORRECTION - FORMAT DATE D'INSCRIPTION")
    print("=" * 80)
    
    try:
        eleve = Eleve.objects.first()
        if not eleve or not eleve.date_inscription:
            print("[INFO] Aucun eleve avec date d'inscription pour le test")
            return True
            
        print(f"Test avec eleve : {eleve.prenom} {eleve.nom}")
        print(f"Date d'inscription en base : {eleve.date_inscription}")
        
        form = EleveForm(instance=eleve)
        html_field = str(form['date_inscription'])
        
        # Recherche de la valeur dans le HTML
        import re
        value_match = re.search(r'value="([^"]*)"', html_field)
        if value_match:
            html_value = value_match.group(1)
            print(f"Valeur date inscription dans HTML : '{html_value}'")
            
            # Vérification du format ISO
            if re.match(r'^\d{4}-\d{2}-\d{2}$', html_value):
                print("[OK] Date d'inscription au format ISO")
                return True
            else:
                print(f"[ERREUR] Date d'inscription pas au format ISO : {html_value}")
                return False
        else:
            print("[ERREUR] Aucune valeur trouvee pour date d'inscription")
            return False
            
    except Exception as e:
        print(f"[ERREUR] Erreur lors du test date inscription : {str(e)}")
        return False

if __name__ == "__main__":
    print("LANCEMENT DU TEST DE CORRECTION - FORMAT DATE")
    
    # Test 1 : Correction date de naissance
    test1_result = test_correction_format_date()
    
    # Test 2 : Correction date d'inscription
    test2_result = test_widget_date_inscription()
    
    print("\n" + "=" * 80)
    print("RESUME DES TESTS DE CORRECTION")
    print("=" * 80)
    print(f"Test 1 - Format date naissance : {'[OK] REUSSI' if test1_result else '[ERREUR] ECHOUE'}")
    print(f"Test 2 - Format date inscription : {'[OK] REUSSI' if test2_result else '[ERREUR] ECHOUE'}")
    
    if test1_result and test2_result:
        print("\nCONCLUSION : CORRECTION DU FORMAT DE DATE REUSSIE")
        print("[OK] Les dates sont maintenant correctement affichees au format ISO")
        print("[OK] Le formulaire de modification recupere bien les dates")
    else:
        print("\nCONCLUSION : PROBLEMES DETECTES DANS LA CORRECTION")
        print("[ERREUR] Verification necessaire des widgets de date")
    
    print("=" * 80)
