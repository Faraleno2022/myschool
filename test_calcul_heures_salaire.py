#!/usr/bin/env python
"""
Script de test pour vérifier l'intégration du calcul des heures dans le bulletin de salaire
"""

import os
import sys
import django
from decimal import Decimal

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.contrib.auth.models import User
from eleves.models import Ecole
from salaires.models import Enseignant, PeriodeSalaire, EtatSalaire, TypeEnseignant
from django.utils import timezone

def test_calcul_heures_salaire():
    """Test du calcul du salaire basé sur les heures mensuelles"""
    
    print("=== Test du Calcul des Heures dans le Bulletin de Salaire ===\n")
    
    # 1. Récupérer une école
    try:
        ecole = Ecole.objects.first()
        if not ecole:
            print("❌ Aucune école trouvée. Veuillez d'abord initialiser les données.")
            return
        print(f"✅ École sélectionnée : {ecole.nom}")
    except Exception as e:
        print(f"❌ Erreur lors de la récupération de l'école : {e}")
        return
    
    # 2. Créer un utilisateur admin si nécessaire
    try:
        admin_user, created = User.objects.get_or_create(
            username='admin_test',
            defaults={
                'email': 'admin@test.com',
                'first_name': 'Admin',
                'last_name': 'Test',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
        print(f"✅ Utilisateur admin : {admin_user.username}")
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'utilisateur : {e}")
        return
    
    # 3. Créer un enseignant de test avec taux horaire et heures mensuelles
    try:
        enseignant_test, created = Enseignant.objects.get_or_create(
            nom='DIALLO',
            prenoms='Mamadou Test Heures',
            defaults={
                'telephone': '+224123456789',
                'email': 'mamadou.diallo.test@ecole.com',
                'ecole': ecole,
                'type_enseignant': TypeEnseignant.SECONDAIRE,
                'taux_horaire': Decimal('15000'),  # 15 000 GNF/heure
                'heures_mensuelles': Decimal('120'),  # 120 heures par mois
                'statut': 'ACTIF',
                'date_embauche': timezone.now().date(),
                'cree_par': admin_user
            }
        )
        
        if created:
            print(f"✅ Enseignant créé : {enseignant_test.nom_complet}")
        else:
            print(f"✅ Enseignant existant : {enseignant_test.nom_complet}")
            
        print(f"   - Type : {enseignant_test.get_type_enseignant_display()}")
        print(f"   - Taux horaire : {enseignant_test.taux_horaire:,} GNF/h")
        print(f"   - Heures mensuelles : {enseignant_test.heures_mensuelles} h")
        print(f"   - Salaire calculé : {enseignant_test.calculer_salaire_mensuel():,} GNF")
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'enseignant : {e}")
        return
    
    # 4. Créer une période de salaire pour le mois courant
    try:
        now = timezone.now()
        periode, created = PeriodeSalaire.objects.get_or_create(
            mois=now.month,
            annee=now.year,
            ecole=ecole,
            defaults={
                'nombre_semaines': Decimal('4.33'),
                'cree_par': admin_user
            }
        )
        
        if created:
            print(f"✅ Période créée : {periode}")
        else:
            print(f"✅ Période existante : {periode}")
            
    except Exception as e:
        print(f"❌ Erreur lors de la création de la période : {e}")
        return
    
    # 5. Calculer l'état de salaire
    try:
        # Supprimer l'ancien état s'il existe
        EtatSalaire.objects.filter(
            enseignant=enseignant_test,
            periode=periode
        ).delete()
        
        # Créer le nouvel état de salaire
        etat_salaire = EtatSalaire.objects.create(
            enseignant=enseignant_test,
            periode=periode,
            calcule_par=admin_user,
            total_heures=enseignant_test.heures_mensuelles_effectives,
            salaire_base=enseignant_test.calculer_salaire_mensuel(),
            salaire_net=enseignant_test.calculer_salaire_mensuel()
        )
        
        print(f"✅ État de salaire créé :")
        print(f"   - ID : {etat_salaire.id}")
        print(f"   - Heures travaillées : {etat_salaire.total_heures} h")
        print(f"   - Salaire de base : {etat_salaire.salaire_base:,} GNF")
        print(f"   - Salaire net : {etat_salaire.salaire_net:,} GNF")
        
    except Exception as e:
        print(f"❌ Erreur lors du calcul de l'état de salaire : {e}")
        return
    
    # 6. Vérifier le calcul
    try:
        calcul_attendu = enseignant_test.taux_horaire * enseignant_test.heures_mensuelles_effectives
        calcul_reel = etat_salaire.salaire_base
        
        print(f"\n=== Vérification du Calcul ===")
        print(f"Formule : {enseignant_test.heures_mensuelles_effectives} h × {enseignant_test.taux_horaire:,} GNF/h")
        print(f"Calcul attendu : {calcul_attendu:,} GNF")
        print(f"Calcul réel : {calcul_reel:,} GNF")
        
        if calcul_attendu == calcul_reel:
            print("✅ Le calcul est CORRECT !")
        else:
            print("❌ Le calcul est INCORRECT !")
            
    except Exception as e:
        print(f"❌ Erreur lors de la vérification : {e}")
        return
    
    # 7. Afficher les informations pour tester l'interface
    print(f"\n=== Test de l'Interface Web ===")
    print(f"Pour tester l'affichage du bulletin de salaire :")
    print(f"1. Accédez à : http://127.0.0.1:8000/salaires/etats/")
    print(f"2. Recherchez l'enseignant : {enseignant_test.nom_complet}")
    print(f"3. Vérifiez l'affichage du calcul détaillé :")
    print(f"   - Heures travaillées : {etat_salaire.total_heures} h")
    print(f"   - Taux horaire : {enseignant_test.taux_horaire:,} GNF/h")
    print(f"   - Calcul : {etat_salaire.total_heures} h × {enseignant_test.taux_horaire:,} GNF/h")
    print(f"   - Salaire de base : {etat_salaire.salaire_base:,} GNF")
    
    print(f"\n🎉 Test terminé avec succès !")

if __name__ == '__main__':
    test_calcul_heures_salaire()
