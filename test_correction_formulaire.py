#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test simple pour vérifier que la correction du formulaire fonctionne
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve
from eleves.forms import EleveForm

def test_correction_formulaire():
    """
    Test simple pour vérifier que le formulaire peut maintenant enregistrer
    """
    print("=" * 60)
    print("TEST DE VERIFICATION - CORRECTION DU FORMULAIRE")
    print("=" * 60)
    
    try:
        # 1. Récupération de l'élève Thierno BAH
        eleve = Eleve.objects.filter(prenom="Thierno", nom="BAH").first()
        if not eleve:
            print("[ERREUR] Eleve Thierno BAH non trouve")
            return False
            
        print(f"[OK] Eleve trouve : {eleve.prenom} {eleve.nom}")
        print(f"   Lieu actuel : {eleve.lieu_naissance}")
        
        # 2. Simulation d'une modification simple
        nouveau_lieu = "Kissidougou" if eleve.lieu_naissance != "Kissidougou" else "Conakry"
        
        # Données du formulaire avec modification
        form_data = {
            'matricule': eleve.matricule,
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': nouveau_lieu,  # MODIFICATION
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d') if eleve.date_inscription else '',
            'statut': eleve.statut,
            'classe': eleve.classe.id if eleve.classe else '',
            'responsable_principal': eleve.responsable_principal.id if eleve.responsable_principal else '',
            'responsable_secondaire': eleve.responsable_secondaire.id if eleve.responsable_secondaire else '',
        }
        
        print(f"[TEST] Modification : '{eleve.lieu_naissance}' -> '{nouveau_lieu}'")
        
        # 3. Test du formulaire
        form = EleveForm(data=form_data, instance=eleve)
        
        if form.is_valid():
            print("[OK] Formulaire valide")
            
            # Sauvegarde
            eleve_modifie = form.save()
            print(f"[OK] Sauvegarde reussie")
            
            # Vérification
            eleve_verifie = Eleve.objects.get(id=eleve.id)
            if eleve_verifie.lieu_naissance == nouveau_lieu:
                print(f"[OK] Modification persistee : {eleve_verifie.lieu_naissance}")
                return True
            else:
                print(f"[ERREUR] Modification non persistee")
                return False
        else:
            print("[ERREUR] Formulaire invalide :")
            for field, errors in form.errors.items():
                print(f"   {field}: {errors}")
            return False
            
    except Exception as e:
        print(f"[ERREUR] Exception : {str(e)}")
        return False

def test_verification_template_corrige():
    """
    Vérification que le template a été corrigé
    """
    print("\n" + "=" * 60)
    print("VERIFICATION DU TEMPLATE CORRIGE")
    print("=" * 60)
    
    try:
        template_path = r"c:\Users\faral\Desktop\GS HADJA_KANFING_DIANÉ\templates\eleves\modifier_eleve.html"
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifications
        checks = [
            ('ID formulaire correct', 'id="eleveForm"' in content),
            ('Bouton save avec action', 'name="action" value="save"' in content),
            ('Bouton save_and_list avec action', 'name="action" value="save_and_list"' in content),
            ('Token CSRF present', '{% csrf_token %}' in content),
            ('Method POST', 'method="post"' in content),
        ]
        
        all_ok = True
        for check_name, check_result in checks:
            status = "[OK]" if check_result else "[ERREUR]"
            print(f"{status} {check_name}")
            if not check_result:
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"[ERREUR] Impossible de verifier le template : {str(e)}")
        return False

if __name__ == "__main__":
    print("LANCEMENT DU TEST DE VERIFICATION")
    
    # Test 1 : Fonctionnement du formulaire
    test1_result = test_correction_formulaire()
    
    # Test 2 : Vérification du template
    test2_result = test_verification_template_corrige()
    
    print("\n" + "=" * 60)
    print("RESULTAT FINAL")
    print("=" * 60)
    print(f"Test formulaire : {'[OK] REUSSI' if test1_result else '[ERREUR] ECHOUE'}")
    print(f"Test template : {'[OK] REUSSI' if test2_result else '[ERREUR] ECHOUE'}")
    
    if test1_result and test2_result:
        print("\n[SUCCES] La correction est effective !")
        print("Le formulaire devrait maintenant enregistrer les modifications.")
    else:
        print("\n[ATTENTION] Des problemes subsistent.")
    
    print("=" * 60)
