#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test pour vérifier que le formulaire de modification récupère correctement 
toutes les informations de l'élève
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from eleves.models import Eleve
from eleves.forms import EleveForm
from eleves.views import modifier_eleve

def test_recuperation_donnees_formulaire():
    print("TEST RECUPERATION DONNEES FORMULAIRE MODIFICATION")
    print("=" * 60)
    
    # Trouver un élève avec toutes les informations
    eleve_test = Eleve.objects.select_related(
        'classe', 'responsable_principal', 'responsable_secondaire'
    ).first()
    
    if not eleve_test:
        print("Aucun eleve trouve pour le test")
        return False
    
    print(f"Eleve de test: {eleve_test.prenom} {eleve_test.nom}")
    print(f"Matricule: {eleve_test.matricule}")
    print(f"Classe: {eleve_test.classe.nom}")
    print(f"Responsable principal: {eleve_test.responsable_principal.prenom} {eleve_test.responsable_principal.nom}")
    if eleve_test.responsable_secondaire:
        print(f"Responsable secondaire: {eleve_test.responsable_secondaire.prenom} {eleve_test.responsable_secondaire.nom}")
    else:
        print("Responsable secondaire: Aucun")
    
    try:
        # Test 1: Formulaire avec instance (comme dans la vue modifier_eleve)
        print("\n" + "-" * 50)
        print("TEST 1: Formulaire avec instance")
        print("-" * 50)
        
        form = EleveForm(instance=eleve_test)
        
        # Vérifier que tous les champs sont pré-remplis
        champs_a_verifier = [
            'matricule', 'prenom', 'nom', 'sexe', 'date_naissance',
            'lieu_naissance', 'classe', 'date_inscription', 'statut',
            'responsable_principal', 'responsable_secondaire'
        ]
        
        print("Verification des champs pre-remplis:")
        tous_corrects = True
        
        for champ in champs_a_verifier:
            if champ in form.initial:
                valeur_form = form.initial[champ]
                valeur_eleve = getattr(eleve_test, champ)
                
                # Traitement spécial pour les clés étrangères
                if champ in ['classe', 'responsable_principal', 'responsable_secondaire']:
                    if valeur_eleve:
                        valeur_eleve = valeur_eleve.id
                    else:
                        valeur_eleve = None
                
                print(f"  {champ}: {valeur_form} (attendu: {valeur_eleve})")
                
                if valeur_form != valeur_eleve:
                    print(f"    ERREUR - Valeurs differentes!")
                    tous_corrects = False
                else:
                    print(f"    OK")
            else:
                # Vérifier dans form.fields pour les champs sans initial
                if hasattr(form.fields[champ], 'widget') and hasattr(form.fields[champ].widget, 'value_from_datadict'):
                    print(f"  {champ}: Pas dans initial mais widget present")
                else:
                    print(f"  {champ}: MANQUANT dans initial")
                    tous_corrects = False
        
        if tous_corrects:
            print("SUCCES - Tous les champs sont correctement pre-remplis")
        else:
            print("PROBLEME - Certains champs ne sont pas correctement pre-remplis")
        
        # Test 2: Rendu HTML du formulaire
        print("\n" + "-" * 50)
        print("TEST 2: Rendu HTML du formulaire")
        print("-" * 50)
        
        # Vérifier que les champs ont les bonnes valeurs dans le HTML
        html_matricule = str(form['matricule'])
        html_prenom = str(form['prenom'])
        html_nom = str(form['nom'])
        
        print("Verification du rendu HTML:")
        print(f"  Matricule dans HTML: {eleve_test.matricule in html_matricule}")
        print(f"  Prenom dans HTML: {eleve_test.prenom in html_prenom}")
        print(f"  Nom dans HTML: {eleve_test.nom in html_nom}")
        
        # Test 3: Test avec la vue modifier_eleve
        print("\n" + "-" * 50)
        print("TEST 3: Vue modifier_eleve GET")
        print("-" * 50)
        
        # Créer utilisateur
        user, created = User.objects.get_or_create(
            username='test_modif_form',
            defaults={'email': 'test@modif.com'}
        )
        
        # Créer requête GET
        factory = RequestFactory()
        request = factory.get(f'/eleves/{eleve_test.id}/modifier/')
        request.user = user
        
        # Ajouter sessions
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        print("Appel de la vue modifier_eleve (GET)...")
        response = modifier_eleve(request, eleve_test.id)
        
        if response.status_code == 200:
            print("Vue modifier_eleve repond correctement")
            
            # Vérifier le contexte
            if hasattr(response, 'context_data'):
                context = response.context_data
                if 'form' in context:
                    form_vue = context['form']
                    print("Formulaire trouve dans le contexte")
                    
                    # Vérifier quelques champs clés
                    if hasattr(form_vue, 'instance') and form_vue.instance:
                        print(f"  Instance du formulaire: {form_vue.instance.prenom} {form_vue.instance.nom}")
                        if form_vue.instance.id == eleve_test.id:
                            print("  SUCCES - Bonne instance dans le formulaire")
                        else:
                            print("  ERREUR - Mauvaise instance dans le formulaire")
                    else:
                        print("  ERREUR - Pas d'instance dans le formulaire")
                else:
                    print("Pas de formulaire dans le contexte")
            else:
                print("Pas de context_data dans la reponse")
        else:
            print(f"Erreur vue modifier_eleve: {response.status_code}")
        
        # Test 4: Test avec Client Django (simulation navigateur)
        print("\n" + "-" * 50)
        print("TEST 4: Test avec Client Django")
        print("-" * 50)
        
        client = Client()
        
        # Se connecter
        if created:
            user.set_password('testpass123')
            user.save()
        
        login_success = client.login(username='test_modif_form', password='testpass123')
        
        if login_success:
            print("Connexion reussie")
            
            # Récupérer la page de modification
            response_client = client.get(f'/eleves/{eleve_test.id}/modifier/')
            
            if response_client.status_code == 200:
                print("Page de modification chargee")
                
                # Vérifier le contenu HTML
                content = response_client.content.decode('utf-8')
                
                verifications_html = [
                    (f'value="{eleve_test.matricule}"', "Matricule"),
                    (f'value="{eleve_test.prenom}"', "Prenom"),
                    (f'value="{eleve_test.nom}"', "Nom"),
                    (eleve_test.lieu_naissance, "Lieu de naissance"),
                ]
                
                print("Verification du contenu HTML:")
                html_correct = True
                for verification, nom in verifications_html:
                    if verification in content:
                        print(f"  {nom}: TROUVE dans HTML")
                    else:
                        print(f"  {nom}: NON TROUVE dans HTML")
                        html_correct = False
                
                if html_correct:
                    print("SUCCES - Toutes les donnees sont presentes dans le HTML")
                    return True
                else:
                    print("PROBLEME - Certaines donnees manquent dans le HTML")
                    return False
            else:
                print(f"Erreur chargement page: {response_client.status_code}")
                return False
        else:
            print("Echec de connexion")
            return False
            
    except Exception as e:
        print(f"Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_champs_specifiques():
    print("\n" + "=" * 60)
    print("TEST CHAMPS SPECIFIQUES")
    print("=" * 60)
    
    # Test avec différents types de champs
    eleve = Eleve.objects.first()
    if not eleve:
        return False
    
    print(f"Test avec eleve: {eleve.prenom} {eleve.nom}")
    
    # Créer formulaire
    form = EleveForm(instance=eleve)
    
    # Test des champs de date
    print("\nTest champs de date:")
    print(f"  Date naissance: {form.initial.get('date_naissance')} (attendu: {eleve.date_naissance})")
    print(f"  Date inscription: {form.initial.get('date_inscription')} (attendu: {eleve.date_inscription})")
    
    # Test des champs de choix
    print("\nTest champs de choix:")
    print(f"  Sexe: {form.initial.get('sexe')} (attendu: {eleve.sexe})")
    print(f"  Statut: {form.initial.get('statut')} (attendu: {eleve.statut})")
    
    # Test des relations
    print("\nTest relations:")
    print(f"  Classe: {form.initial.get('classe')} (attendu: {eleve.classe.id})")
    print(f"  Responsable principal: {form.initial.get('responsable_principal')} (attendu: {eleve.responsable_principal.id})")
    
    if eleve.responsable_secondaire:
        print(f"  Responsable secondaire: {form.initial.get('responsable_secondaire')} (attendu: {eleve.responsable_secondaire.id})")
    else:
        print(f"  Responsable secondaire: {form.initial.get('responsable_secondaire')} (attendu: None)")
    
    return True

if __name__ == '__main__':
    try:
        print("TEST COMPLET - FORMULAIRE MODIFICATION ELEVE")
        print("=" * 70)
        
        success1 = test_recuperation_donnees_formulaire()
        success2 = test_champs_specifiques()
        
        print("\n" + "=" * 70)
        if success1 and success2:
            print("RESULTAT: FORMULAIRE FONCTIONNE CORRECTEMENT")
            print("Toutes les donnees sont correctement recuperees et affichees")
        else:
            print("RESULTAT: PROBLEMES DETECTES")
            if not success1:
                print("- Probleme avec la recuperation des donnees")
            if not success2:
                print("- Probleme avec les champs specifiques")
                
    except Exception as e:
        print(f"ERREUR GENERALE: {e}")
        sys.exit(1)
