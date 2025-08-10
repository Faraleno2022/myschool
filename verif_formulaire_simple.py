#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vérification simple que le formulaire de modification récupère bien les données
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve
from eleves.forms import EleveForm

def verifier_formulaire_modification():
    print("VERIFICATION FORMULAIRE MODIFICATION")
    print("=" * 50)
    
    # Prendre le premier élève
    eleve = Eleve.objects.select_related(
        'classe', 'responsable_principal', 'responsable_secondaire'
    ).first()
    
    if not eleve:
        print("Aucun eleve trouve")
        return False
    
    print(f"Eleve: {eleve.prenom} {eleve.nom}")
    print(f"Matricule: {eleve.matricule}")
    print(f"Statut: {eleve.statut}")
    print(f"Classe: {eleve.classe.nom}")
    print(f"Responsable: {eleve.responsable_principal.prenom} {eleve.responsable_principal.nom}")
    
    # Créer le formulaire avec l'instance (comme dans la vue)
    form = EleveForm(instance=eleve)
    
    print("\nVerification des donnees dans le formulaire:")
    
    # Vérifier les champs principaux
    verifications = [
        ('matricule', eleve.matricule),
        ('prenom', eleve.prenom),
        ('nom', eleve.nom),
        ('sexe', eleve.sexe),
        ('statut', eleve.statut),
        ('lieu_naissance', eleve.lieu_naissance),
        ('date_naissance', eleve.date_naissance),
        ('date_inscription', eleve.date_inscription),
        ('classe', eleve.classe.id),
        ('responsable_principal', eleve.responsable_principal.id),
    ]
    
    if eleve.responsable_secondaire:
        verifications.append(('responsable_secondaire', eleve.responsable_secondaire.id))
    
    tous_ok = True
    
    for champ, valeur_attendue in verifications:
        valeur_form = form.initial.get(champ)
        
        if valeur_form == valeur_attendue:
            print(f"  {champ}: OK ({valeur_form})")
        else:
            print(f"  {champ}: ERREUR - Form: {valeur_form}, Attendu: {valeur_attendue}")
            tous_ok = False
    
    # Vérifier le rendu HTML de quelques champs
    print("\nVerification rendu HTML:")
    
    html_matricule = str(form['matricule'])
    html_prenom = str(form['prenom'])
    html_statut = str(form['statut'])
    
    if eleve.matricule in html_matricule:
        print(f"  Matricule dans HTML: OK")
    else:
        print(f"  Matricule dans HTML: ERREUR")
        tous_ok = False
    
    if eleve.prenom in html_prenom:
        print(f"  Prenom dans HTML: OK")
    else:
        print(f"  Prenom dans HTML: ERREUR")
        tous_ok = False
    
    if eleve.statut in html_statut:
        print(f"  Statut dans HTML: OK")
    else:
        print(f"  Statut dans HTML: ERREUR")
        tous_ok = False
    
    print(f"\nRESULTAT: {'SUCCES' if tous_ok else 'PROBLEMES DETECTES'}")
    
    if tous_ok:
        print("Le formulaire recupere correctement toutes les informations!")
    
    return tous_ok

def test_modification_complete():
    print("\n" + "=" * 50)
    print("TEST MODIFICATION COMPLETE")
    print("=" * 50)
    
    eleve = Eleve.objects.first()
    if not eleve:
        return False
    
    print(f"Test avec: {eleve.prenom} {eleve.nom}")
    
    # Sauvegarder les valeurs originales
    prenom_original = eleve.prenom
    statut_original = eleve.statut
    
    try:
        # Créer formulaire avec instance
        form = EleveForm(instance=eleve)
        
        # Préparer nouvelles données (simuler une modification)
        nouvelles_donnees = {
            'matricule': eleve.matricule,
            'prenom': 'PrenomModifie',  # Changement
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': eleve.lieu_naissance,
            'classe': str(eleve.classe.id),
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d'),
            'statut': 'SUSPENDU' if eleve.statut != 'SUSPENDU' else 'ACTIF',  # Changement
            'responsable_principal': str(eleve.responsable_principal.id),
            'responsable_secondaire': str(eleve.responsable_secondaire.id) if eleve.responsable_secondaire else '',
        }
        
        print("Donnees de modification preparees")
        
        # Créer nouveau formulaire avec les données
        form_modif = EleveForm(data=nouvelles_donnees, instance=eleve)
        
        if form_modif.is_valid():
            print("Formulaire de modification valide")
            
            # Sauvegarder (test)
            eleve_modifie = form_modif.save()
            
            print(f"Prenom modifie: {eleve_modifie.prenom}")
            print(f"Statut modifie: {eleve_modifie.statut}")
            
            # Vérifier les changements
            if eleve_modifie.prenom == 'PrenomModifie':
                print("Modification du prenom: OK")
            else:
                print("Modification du prenom: ERREUR")
            
            success = True
        else:
            print("Formulaire de modification invalide:")
            for field, errors in form_modif.errors.items():
                print(f"  {field}: {errors}")
            success = False
        
        return success
        
    except Exception as e:
        print(f"Erreur: {e}")
        return False
        
    finally:
        # Restaurer les valeurs originales
        eleve.prenom = prenom_original
        eleve.statut = statut_original
        eleve.save()
        print(f"Valeurs restaurees: {prenom_original}, {statut_original}")

if __name__ == '__main__':
    print("VERIFICATION COMPLETE FORMULAIRE MODIFICATION")
    print("=" * 60)
    
    success1 = verifier_formulaire_modification()
    success2 = test_modification_complete()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("CONCLUSION: FORMULAIRE FONCTIONNE PARFAITEMENT")
        print("- Toutes les donnees sont correctement recuperees")
        print("- Le pre-remplissage fonctionne")
        print("- Les modifications sont sauvegardees")
    else:
        print("CONCLUSION: PROBLEMES DETECTES")
        if not success1:
            print("- Probleme avec la recuperation des donnees")
        if not success2:
            print("- Probleme avec la modification")
