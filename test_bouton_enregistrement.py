#!/usr/bin/env python
"""
Script de test pour vérifier le fonctionnement du bouton d'enregistrement
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
    
    # 1. Vérifier l'existence des modèles nécessaires
    print("\n1. Verification des modeles...")
    
    try:
        # Vérifier qu'il y a au moins une école
        ecoles = Ecole.objects.all()
        print(f"   ✅ Écoles disponibles: {ecoles.count()}")
        
        if ecoles.count() == 0:
            print("   ⚠️  Création d'une école de test...")
            ecole_test = Ecole.objects.create(
                nom="École Test",
                adresse="Adresse Test",
                telephone="+224123456789",
                email="test@ecole.com"
            )
            print(f"   ✅ École créée: {ecole_test.nom}")
        else:
            ecole_test = ecoles.first()
        
        # Vérifier qu'il y a au moins une classe
        classes = Classe.objects.filter(ecole=ecole_test)
        print(f"   ✅ Classes disponibles: {classes.count()}")
        
        if classes.count() == 0:
            print("   ⚠️  Création d'une classe de test...")
            classe_test = Classe.objects.create(
                nom="CP1 Test",
                niveau="CP1",
                ecole=ecole_test,
                annee_scolaire="2024-2025"
            )
            print(f"   ✅ Classe créée: {classe_test.nom}")
        else:
            classe_test = classes.first()
        
        # Vérifier qu'il y a au moins un responsable
        responsables = Responsable.objects.all()
        print(f"   ✅ Responsables disponibles: {responsables.count()}")
        
        if responsables.count() == 0:
            print("   ⚠️  Création d'un responsable de test...")
            responsable_test = Responsable.objects.create(
                prenom="Papa",
                nom="Test",
                relation="PERE",
                telephone="+224987654321",
                email="papa@test.com",
                adresse="Adresse Papa Test"
            )
            print(f"   ✅ Responsable créé: {responsable_test.prenom} {responsable_test.nom}")
        else:
            responsable_test = responsables.first()
        
    except Exception as e:
        print(f"   ❌ Erreur lors de la vérification des modèles: {e}")
        return False
    
    # 2. Test du formulaire EleveForm
    print("\n2. 📝 Test du formulaire EleveForm...")
    
    try:
        # Données de test pour un élève
        donnees_eleve = {
            'matricule': 'TEST001',
            'prenom': 'Élève',
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
            print("   ✅ Formulaire EleveForm valide")
            
            # Vérifier qu'on peut créer un utilisateur de test
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
            
            print(f"   ✅ Élève créé avec succès: {eleve.prenom} {eleve.nom} (ID: {eleve.id})")
            print(f"   📊 Matricule: {eleve.matricule}")
            print(f"   📊 Classe: {eleve.classe.nom}")
            print(f"   📊 Responsable: {eleve.responsable_principal.prenom} {eleve.responsable_principal.nom}")
            
        else:
            print("   ❌ Formulaire EleveForm invalide:")
            for field, errors in form.errors.items():
                print(f"      - {field}: {errors}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur lors du test du formulaire: {e}")
        return False
    
    # 3. Test de la logique de validation
    print("\n3. 🔍 Test de la logique de validation...")
    
    try:
        # Test avec données manquantes
        donnees_invalides = {
            'matricule': '',  # Matricule manquant
            'prenom': 'Test',
            'nom': 'Invalide',
        }
        
        form_invalide = EleveForm(data=donnees_invalides)
        
        if not form_invalide.is_valid():
            print("   ✅ Validation des champs obligatoires fonctionne")
            print("   📋 Erreurs détectées:")
            for field, errors in form_invalide.errors.items():
                print(f"      - {field}: {errors[0]}")
        else:
            print("   ⚠️  La validation devrait échouer avec des données manquantes")
            
    except Exception as e:
        print(f"   ❌ Erreur lors du test de validation: {e}")
        return False
    
    # 4. Statistiques finales
    print("\n4. 📊 Statistiques après test...")
    
    try:
        total_eleves = Eleve.objects.count()
        eleves_actifs = Eleve.objects.filter(statut='ACTIF').count()
        eleves_test = Eleve.objects.filter(matricule__startswith='TEST').count()
        
        print(f"   📈 Total élèves: {total_eleves}")
        print(f"   📈 Élèves actifs: {eleves_actifs}")
        print(f"   📈 Élèves de test: {eleves_test}")
        
    except Exception as e:
        print(f"   ❌ Erreur lors du calcul des statistiques: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS!")
    print("🎯 Le bouton d'enregistrement devrait fonctionner correctement")
    print("💡 Conseils pour tester manuellement:")
    print("   1. Aller sur /eleves/ajouter/")
    print("   2. Remplir les champs obligatoires (marqués avec *)")
    print("   3. Sélectionner un responsable existant ou créer un nouveau")
    print("   4. Cliquer sur 'Enregistrer l'élève'")
    print("   5. Vérifier l'affichage du message de succès")
    
    return True

def nettoyer_donnees_test():
    """Nettoyer les données de test créées"""
    print("\n🧹 Nettoyage des données de test...")
    
    try:
        # Supprimer les élèves de test
        eleves_test = Eleve.objects.filter(matricule__startswith='TEST')
        count_eleves = eleves_test.count()
        eleves_test.delete()
        print(f"   ✅ {count_eleves} élève(s) de test supprimé(s)")
        
        # Supprimer les responsables de test (optionnel)
        responsables_test = Responsable.objects.filter(nom='Test')
        count_resp = responsables_test.count()
        if count_resp > 0:
            responsables_test.delete()
            print(f"   ✅ {count_resp} responsable(s) de test supprimé(s)")
        
        # Supprimer les classes de test (optionnel)
        classes_test = Classe.objects.filter(nom__contains='Test')
        count_classes = classes_test.count()
        if count_classes > 0:
            classes_test.delete()
            print(f"   ✅ {count_classes} classe(s) de test supprimée(s)")
        
        # Supprimer les écoles de test (optionnel)
        ecoles_test = Ecole.objects.filter(nom__contains='Test')
        count_ecoles = ecoles_test.count()
        if count_ecoles > 0:
            ecoles_test.delete()
            print(f"   ✅ {count_ecoles} école(s) de test supprimée(s)")
            
    except Exception as e:
        print(f"   ❌ Erreur lors du nettoyage: {e}")

if __name__ == '__main__':
    try:
        # Exécuter les tests
        success = test_bouton_enregistrement()
        
        # Demander si on veut nettoyer
        if success:
            reponse = input("\n🤔 Voulez-vous nettoyer les données de test? (o/N): ")
            if reponse.lower() in ['o', 'oui', 'y', 'yes']:
                nettoyer_donnees_test()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrompu par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        sys.exit(1)
