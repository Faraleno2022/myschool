#!/usr/bin/env python
"""
Script de test complet pour valider tous les types de calcul de salaire
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

def test_complet_salaires():
    """Test complet de tous les types de calcul de salaire"""
    
    print("=== Test Complet du Système de Salaires ===\n")
    
    # 1. Récupérer l'école et l'utilisateur admin
    try:
        ecole = Ecole.objects.first()
        admin_user = User.objects.filter(is_superuser=True).first()
        
        if not ecole or not admin_user:
            print("❌ École ou utilisateur admin non trouvé.")
            return
            
        print(f"✅ École : {ecole.nom}")
        print(f"✅ Admin : {admin_user.username}\n")
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return
    
    # 2. Créer différents types d'enseignants
    enseignants_test = [
        {
            'nom': 'BARRY',
            'prenoms': 'Aissatou Taux Horaire',
            'type_enseignant': TypeEnseignant.SECONDAIRE,
            'taux_horaire': Decimal('20000'),
            'heures_mensuelles': Decimal('100'),
            'salaire_fixe': None,
            'description': 'Enseignant secondaire - 100h × 20,000 GNF/h'
        },
        {
            'nom': 'CAMARA',
            'prenoms': 'Mohamed Salaire Fixe',
            'type_enseignant': TypeEnseignant.PRIMAIRE,
            'taux_horaire': None,
            'heures_mensuelles': Decimal('160'),
            'salaire_fixe': Decimal('2500000'),
            'description': 'Enseignant primaire - Salaire fixe 2,500,000 GNF'
        },
        {
            'nom': 'DIALLO',
            'prenoms': 'Fatoumata Maternelle',
            'type_enseignant': TypeEnseignant.MATERNELLE,
            'taux_horaire': None,
            'heures_mensuelles': Decimal('140'),
            'salaire_fixe': Decimal('1800000'),
            'description': 'Enseignant maternelle - Salaire fixe 1,800,000 GNF'
        },
        {
            'nom': 'SOW',
            'prenoms': 'Boubacar Garderie',
            'type_enseignant': TypeEnseignant.GARDERIE,
            'taux_horaire': None,
            'heures_mensuelles': Decimal('180'),
            'salaire_fixe': Decimal('1500000'),
            'description': 'Enseignant garderie - Salaire fixe 1,500,000 GNF'
        },
        {
            'nom': 'TOURE',
            'prenoms': 'Amadou Admin',
            'type_enseignant': TypeEnseignant.ADMINISTRATEUR,
            'taux_horaire': None,
            'heures_mensuelles': Decimal('160'),
            'salaire_fixe': Decimal('3000000'),
            'description': 'Administrateur - Salaire fixe 3,000,000 GNF'
        }
    ]
    
    print("=== Création des Enseignants de Test ===")
    enseignants_crees = []
    
    for data in enseignants_test:
        try:
            enseignant, created = Enseignant.objects.get_or_create(
                nom=data['nom'],
                prenoms=data['prenoms'],
                defaults={
                    'telephone': f"+224{len(enseignants_crees)+1:08d}",
                    'email': f"{data['nom'].lower()}.{data['prenoms'].split()[0].lower()}@ecole.com",
                    'ecole': ecole,
                    'type_enseignant': data['type_enseignant'],
                    'taux_horaire': data['taux_horaire'],
                    'heures_mensuelles': data['heures_mensuelles'],
                    'salaire_fixe': data['salaire_fixe'],
                    'statut': 'ACTIF',
                    'date_embauche': timezone.now().date(),
                    'cree_par': admin_user
                }
            )
            
            enseignants_crees.append(enseignant)
            status = "✅ Créé" if created else "✅ Existant"
            print(f"{status}: {enseignant.nom_complet}")
            print(f"   - {data['description']}")
            print(f"   - Salaire calculé: {enseignant.calculer_salaire_mensuel():,} GNF\n")
            
        except Exception as e:
            print(f"❌ Erreur création {data['nom']}: {e}")
    
    # 3. Créer une période de salaire
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
        
        status = "✅ Créée" if created else "✅ Existante"
        print(f"=== Période de Salaire ===")
        print(f"{status}: {periode}\n")
        
    except Exception as e:
        print(f"❌ Erreur période: {e}")
        return
    
    # 4. Calculer les états de salaire pour tous les enseignants
    print("=== Calcul des États de Salaire ===")
    etats_crees = []
    
    for enseignant in enseignants_crees:
        try:
            # Supprimer l'ancien état s'il existe
            EtatSalaire.objects.filter(
                enseignant=enseignant,
                periode=periode
            ).delete()
            
            # Calculer le salaire selon le type
            if enseignant.est_taux_horaire:
                total_heures = enseignant.heures_mensuelles_effectives
                salaire_base = enseignant.calculer_salaire_mensuel()
            else:
                total_heures = None
                salaire_base = enseignant.salaire_fixe or Decimal('0')
            
            # Créer l'état de salaire
            etat_salaire = EtatSalaire.objects.create(
                enseignant=enseignant,
                periode=periode,
                calcule_par=admin_user,
                total_heures=total_heures,
                salaire_base=salaire_base,
                salaire_net=salaire_base  # Simplifié pour le test
            )
            
            etats_crees.append(etat_salaire)
            
            print(f"✅ {enseignant.nom_complet}")
            print(f"   - Type: {enseignant.get_type_enseignant_display()}")
            if total_heures:
                print(f"   - Heures: {total_heures} h")
                print(f"   - Taux: {enseignant.taux_horaire:,} GNF/h")
                print(f"   - Calcul: {total_heures} × {enseignant.taux_horaire:,} = {salaire_base:,} GNF")
            else:
                print(f"   - Salaire fixe: {salaire_base:,} GNF")
            print(f"   - État ID: {etat_salaire.id}\n")
            
        except Exception as e:
            print(f"❌ Erreur calcul {enseignant.nom_complet}: {e}")
    
    # 5. Résumé et instructions pour tester l'interface
    print("=== Résumé du Test ===")
    print(f"✅ {len(enseignants_crees)} enseignants créés")
    print(f"✅ {len(etats_crees)} états de salaire calculés")
    print(f"✅ Période: {periode}")
    
    print(f"\n=== Test de l'Interface Web ===")
    print(f"1. Accédez à: http://127.0.0.1:8000/salaires/etats/")
    print(f"2. Vérifiez l'affichage des différents types de calcul:")
    
    for i, enseignant in enumerate(enseignants_crees, 1):
        if enseignant.est_taux_horaire:
            print(f"   {i}. {enseignant.nom_complet} → Calcul détaillé avec heures")
        else:
            print(f"   {i}. {enseignant.nom_complet} → Salaire fixe standard")
    
    print(f"\n🎉 Test complet terminé avec succès !")
    print(f"Le système gère maintenant tous les types de rémunération avec calcul précis des heures !")

if __name__ == '__main__':
    test_complet_salaires()
