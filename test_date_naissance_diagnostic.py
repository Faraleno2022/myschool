#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test pour diagnostiquer le problème de récupération de la date de naissance
dans le formulaire de modification d'élève
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve
from eleves.forms import EleveForm

def test_date_naissance_recuperation():
    """
    Test pour vérifier la récupération de la date de naissance
    """
    print("=" * 80)
    print("DIAGNOSTIC - RECUPERATION DATE DE NAISSANCE DANS FORMULAIRE")
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
        print(f"   Type de la date : {type(eleve.date_naissance)}")
        
        if eleve.date_naissance:
            print(f"   Date formatee : {eleve.date_naissance.strftime('%Y-%m-%d')}")
        else:
            print("   [ATTENTION] Date de naissance est None/vide")
        
        # 2. Test du formulaire avec instance
        print("\nETAPE 2 : Test du formulaire avec instance")
        form = EleveForm(instance=eleve)
        
        # Vérification des données initiales du formulaire
        print("Donnees initiales du formulaire :")
        for field_name, field_value in form.initial.items():
            if 'date' in field_name.lower():
                print(f"   {field_name}: {field_value} (type: {type(field_value)})")
        
        # 3. Vérification spécifique du champ date_naissance
        print("\nETAPE 3 : Verification specifique du champ date_naissance")
        
        if 'date_naissance' in form.fields:
            field = form.fields['date_naissance']
            print(f"[OK] Champ date_naissance existe dans le formulaire")
            print(f"   Type de widget : {type(field.widget)}")
            print(f"   Widget attrs : {field.widget.attrs}")
            
            # Valeur initiale du champ
            initial_value = form.initial.get('date_naissance')
            print(f"   Valeur initiale : {initial_value}")
            
            # Vérification du rendu HTML
            html_field = form['date_naissance']
            print(f"   HTML du champ : {str(html_field)[:200]}...")
            
        else:
            print("[ERREUR] Champ date_naissance n'existe pas dans le formulaire")
            return False
        
        # 4. Test de rendu complet du formulaire
        print("\nETAPE 4 : Test de rendu complet du formulaire")
        
        try:
            form_html = str(form)
            if 'date_naissance' in form_html:
                print("[OK] Le champ date_naissance est present dans le HTML du formulaire")
                
                # Recherche de la valeur dans le HTML
                import re
                value_match = re.search(r'name="date_naissance"[^>]*value="([^"]*)"', form_html)
                if value_match:
                    html_value = value_match.group(1)
                    print(f"   Valeur dans le HTML : '{html_value}'")
                    
                    if html_value:
                        print("[OK] La date de naissance a une valeur dans le HTML")
                    else:
                        print("[PROBLEME] La date de naissance est vide dans le HTML")
                else:
                    print("[PROBLEME] Aucune valeur trouvee dans l'attribut value du champ")
            else:
                print("[ERREUR] Le champ date_naissance n'est pas present dans le HTML")
                
        except Exception as e:
            print(f"[ERREUR] Erreur lors du rendu HTML : {str(e)}")
        
        # 5. Test avec données POST simulées
        print("\nETAPE 5 : Test avec donnees POST simulees")
        
        post_data = {
            'matricule': eleve.matricule,
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'statut': eleve.statut,
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d') if eleve.date_naissance else '',
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d') if eleve.date_inscription else '',
            'lieu_naissance': eleve.lieu_naissance or '',
            'classe': eleve.classe.id if eleve.classe else '',
            'responsable_principal': eleve.responsable_principal.id if eleve.responsable_principal else '',
            'responsable_secondaire': eleve.responsable_secondaire.id if eleve.responsable_secondaire else '',
        }
        
        print("Donnees POST simulees :")
        for key, value in post_data.items():
            if 'date' in key:
                print(f"   {key}: {value}")
        
        form_post = EleveForm(data=post_data, instance=eleve)
        
        if form_post.is_valid():
            print("[OK] Formulaire avec donnees POST est valide")
            
            # Vérification de la date dans les données nettoyées
            cleaned_date = form_post.cleaned_data.get('date_naissance')
            print(f"   Date nettoyee : {cleaned_date}")
            
        else:
            print("[ERREUR] Formulaire avec donnees POST invalide :")
            for field, errors in form_post.errors.items():
                print(f"   {field}: {errors}")
        
        return True
        
    except Exception as e:
        print(f"\n[ERREUR] Erreur lors du diagnostic : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_widget_date_configuration():
    """
    Test pour vérifier la configuration du widget de date
    """
    print("\n" + "=" * 80)
    print("DIAGNOSTIC - CONFIGURATION DU WIDGET DE DATE")
    print("=" * 80)
    
    try:
        from eleves.forms import EleveForm
        
        # Création d'un formulaire vide pour examiner la configuration
        form = EleveForm()
        
        if 'date_naissance' in form.fields:
            field = form.fields['date_naissance']
            widget = field.widget
            
            print(f"Type de widget : {type(widget)}")
            print(f"Attributs du widget : {widget.attrs}")
            print(f"Format du widget : {getattr(widget, 'format', 'Non defini')}")
            
            # Test de rendu du widget avec une date
            from datetime import date
            test_date = date(2008, 12, 25)
            
            try:
                rendered = widget.render('date_naissance', test_date)
                print(f"Rendu du widget avec date test : {rendered[:200]}...")
                
                # Vérification de la présence de la valeur
                if '2008-12-25' in rendered:
                    print("[OK] La date est correctement rendue dans le widget")
                else:
                    print("[PROBLEME] La date n'est pas visible dans le rendu du widget")
                    
            except Exception as e:
                print(f"[ERREUR] Erreur lors du rendu du widget : {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors du test du widget : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("LANCEMENT DU DIAGNOSTIC - DATE DE NAISSANCE")
    
    # Test 1 : Récupération de la date
    test1_result = test_date_naissance_recuperation()
    
    # Test 2 : Configuration du widget
    test2_result = test_widget_date_configuration()
    
    print("\n" + "=" * 80)
    print("RESUME DU DIAGNOSTIC")
    print("=" * 80)
    print(f"Test 1 - Recuperation date : {'[OK] REUSSI' if test1_result else '[ERREUR] ECHOUE'}")
    print(f"Test 2 - Configuration widget : {'[OK] REUSSI' if test2_result else '[ERREUR] ECHOUE'}")
    
    if test1_result and test2_result:
        print("\n[INFO] Diagnostic complete - verifier les details ci-dessus")
    else:
        print("\n[ATTENTION] Problemes detectes - voir les erreurs ci-dessus")
    
    print("=" * 80)
