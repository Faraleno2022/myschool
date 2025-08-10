#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test simple pour identifier le problème de mise à jour des statuts
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve

def test_statut_simple():
    print("TEST SIMPLE - MISE A JOUR STATUT")
    print("=" * 40)
    
    # Trouver un élève
    eleve = Eleve.objects.first()
    if not eleve:
        print("Aucun eleve trouve")
        return False
    
    print(f"Eleve: {eleve.prenom} {eleve.nom}")
    print(f"Statut actuel: {eleve.statut}")
    
    # Sauvegarder l'original
    statut_original = eleve.statut
    
    try:
        # Modifier le statut
        nouveau_statut = 'SUSPENDU' if statut_original != 'SUSPENDU' else 'ACTIF'
        eleve.statut = nouveau_statut
        eleve.save()
        
        print(f"Statut modifie vers: {nouveau_statut}")
        
        # Vérifier en base
        eleve_verifie = Eleve.objects.get(id=eleve.id)
        print(f"Statut en base: {eleve_verifie.statut}")
        
        # Test de la requête de la liste
        print("\nTest requete liste:")
        eleves_liste = Eleve.objects.select_related(
            'classe', 'classe__ecole', 'responsable_principal', 'responsable_secondaire'
        ).prefetch_related('paiements').order_by('nom', 'prenom')
        
        eleve_dans_liste = None
        for e in eleves_liste:
            if e.id == eleve.id:
                eleve_dans_liste = e
                break
        
        if eleve_dans_liste:
            print(f"Eleve trouve dans liste: {eleve_dans_liste.prenom} {eleve_dans_liste.nom}")
            print(f"Statut dans liste: {eleve_dans_liste.statut}")
            
            if eleve_dans_liste.statut == nouveau_statut:
                print("SUCCES - Statut correct dans la requete liste")
                return True
            else:
                print("PROBLEME - Statut incorrect dans la requete liste")
                return False
        else:
            print("PROBLEME - Eleve non trouve dans la requete liste")
            return False
            
    except Exception as e:
        print(f"Erreur: {e}")
        return False
        
    finally:
        # Restaurer
        eleve.statut = statut_original
        eleve.save()
        print(f"\nStatut restaure: {statut_original}")

def test_modification_via_formulaire():
    print("\n" + "=" * 40)
    print("TEST MODIFICATION VIA FORMULAIRE")
    print("=" * 40)
    
    from eleves.forms import EleveForm
    
    # Trouver un élève
    eleve = Eleve.objects.first()
    if not eleve:
        print("Aucun eleve trouve")
        return False
    
    print(f"Eleve: {eleve.prenom} {eleve.nom}")
    print(f"Statut actuel: {eleve.statut}")
    
    statut_original = eleve.statut
    
    try:
        # Préparer données de modification
        nouveau_statut = 'EXCLU' if statut_original != 'EXCLU' else 'ACTIF'
        
        donnees = {
            'matricule': eleve.matricule,
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'sexe': eleve.sexe,
            'date_naissance': eleve.date_naissance.strftime('%Y-%m-%d'),
            'lieu_naissance': eleve.lieu_naissance,
            'classe': str(eleve.classe.id),
            'date_inscription': eleve.date_inscription.strftime('%Y-%m-%d'),
            'statut': nouveau_statut,  # Nouveau statut
            'responsable_principal': str(eleve.responsable_principal.id),
            'responsable_secondaire': str(eleve.responsable_secondaire.id) if eleve.responsable_secondaire else '',
        }
        
        print(f"Modification vers statut: {nouveau_statut}")
        
        # Test du formulaire
        form = EleveForm(data=donnees, instance=eleve)
        
        if form.is_valid():
            print("Formulaire valide")
            
            # Sauvegarder
            eleve_modifie = form.save()
            print(f"Statut apres save(): {eleve_modifie.statut}")
            
            # Vérifier en base
            eleve_base = Eleve.objects.get(id=eleve.id)
            print(f"Statut en base: {eleve_base.statut}")
            
            # Test requête liste après modification
            print("\nTest requete liste apres modification:")
            eleves_liste = Eleve.objects.select_related(
                'classe', 'classe__ecole', 'responsable_principal', 'responsable_secondaire'
            ).prefetch_related('paiements').order_by('nom', 'prenom')
            
            eleve_dans_liste = None
            for e in eleves_liste:
                if e.id == eleve.id:
                    eleve_dans_liste = e
                    break
            
            if eleve_dans_liste:
                print(f"Statut dans requete liste: {eleve_dans_liste.statut}")
                
                if eleve_dans_liste.statut == nouveau_statut:
                    print("SUCCES - Statut correct apres modification formulaire")
                    return True
                else:
                    print("PROBLEME - Statut incorrect apres modification formulaire")
                    return False
            else:
                print("PROBLEME - Eleve non trouve dans requete liste")
                return False
        else:
            print("Formulaire invalide:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
            return False
            
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restaurer
        eleve.statut = statut_original
        eleve.save()
        print(f"\nStatut restaure: {statut_original}")

if __name__ == '__main__':
    try:
        print("DIAGNOSTIC SIMPLE - STATUTS LISTE ELEVES")
        print("=" * 50)
        
        success1 = test_statut_simple()
        success2 = test_modification_via_formulaire()
        
        print("\n" + "=" * 50)
        if success1 and success2:
            print("RESULTAT: AUCUN PROBLEME DETECTE")
            print("Les statuts se mettent a jour correctement")
            print("Le probleme pourrait etre cote navigateur/cache")
        else:
            print("RESULTAT: PROBLEME DETECTE")
            if not success1:
                print("- Probleme avec modification directe")
            if not success2:
                print("- Probleme avec modification via formulaire")
                
    except Exception as e:
        print(f"ERREUR: {e}")
        sys.exit(1)
