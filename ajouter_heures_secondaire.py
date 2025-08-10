#!/usr/bin/env python
"""
Script pour ajouter les heures mensuelles aux enseignants du secondaire existants
"""

import os
import sys
import django
from decimal import Decimal

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from salaires.models import Enseignant, TypeEnseignant

def ajouter_heures_secondaire():
    """Ajouter les heures mensuelles aux enseignants du secondaire"""
    
    print("=== Ajout des Heures Mensuelles pour les Enseignants du Secondaire ===\n")
    
    # 1. Récupérer tous les enseignants du secondaire
    try:
        enseignants_secondaire = Enseignant.objects.filter(
            type_enseignant=TypeEnseignant.SECONDAIRE,
            statut='ACTIF'
        )
        
        print(f"✅ Trouvé {enseignants_secondaire.count()} enseignant(s) du secondaire actif(s)")
        
        if enseignants_secondaire.count() == 0:
            print("ℹ️  Aucun enseignant du secondaire trouvé.")
            return
            
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des enseignants : {e}")
        return
    
    # 2. Traiter chaque enseignant du secondaire
    print("\n=== Traitement des Enseignants ===")
    
    enseignants_mis_a_jour = 0
    enseignants_deja_configures = 0
    
    for enseignant in enseignants_secondaire:
        try:
            print(f"\n📋 {enseignant.nom_complet}")
            print(f"   - Taux horaire : {enseignant.taux_horaire or 'Non défini'}")
            print(f"   - Heures actuelles : {enseignant.heures_mensuelles or 'Non définies'}")
            
            # Vérifier si les heures sont déjà définies
            if enseignant.heures_mensuelles and enseignant.heures_mensuelles > 0:
                print(f"   ✅ Déjà configuré avec {enseignant.heures_mensuelles} heures")
                enseignants_deja_configures += 1
                continue
            
            # Définir les heures par défaut (120h pour le secondaire)
            heures_defaut = Decimal('120')
            
            # Demander confirmation pour chaque enseignant
            print(f"   🔄 Attribution de {heures_defaut} heures mensuelles par défaut")
            
            # Mettre à jour l'enseignant
            enseignant.heures_mensuelles = heures_defaut
            enseignant.save()
            
            # Calculer le nouveau salaire si taux horaire défini
            if enseignant.taux_horaire:
                nouveau_salaire = enseignant.calculer_salaire_mensuel()
                print(f"   💰 Nouveau salaire calculé : {nouveau_salaire:,} GNF")
                print(f"   📊 Calcul : {heures_defaut} h × {enseignant.taux_horaire:,} GNF/h")
            else:
                print(f"   ⚠️  Taux horaire non défini - salaire non calculable")
            
            print(f"   ✅ Mis à jour avec succès")
            enseignants_mis_a_jour += 1
            
        except Exception as e:
            print(f"   ❌ Erreur lors de la mise à jour : {e}")
    
    # 3. Résumé des modifications
    print(f"\n=== Résumé des Modifications ===")
    print(f"✅ Enseignants mis à jour : {enseignants_mis_a_jour}")
    print(f"ℹ️  Enseignants déjà configurés : {enseignants_deja_configures}")
    print(f"📊 Total traité : {enseignants_mis_a_jour + enseignants_deja_configures}")
    
    # 4. Vérification finale
    if enseignants_mis_a_jour > 0:
        print(f"\n=== Vérification Finale ===")
        
        enseignants_avec_heures = Enseignant.objects.filter(
            type_enseignant=TypeEnseignant.SECONDAIRE,
            statut='ACTIF',
            heures_mensuelles__gt=0
        )
        
        print(f"✅ Enseignants du secondaire avec heures définies : {enseignants_avec_heures.count()}")
        
        for enseignant in enseignants_avec_heures:
            salaire = enseignant.calculer_salaire_mensuel() if enseignant.taux_horaire else "Non calculable"
            print(f"   - {enseignant.nom_complet} : {enseignant.heures_mensuelles}h → {salaire}")
    
    # 5. Instructions pour la suite
    print(f"\n=== Instructions pour la Suite ===")
    print(f"1. Vérifiez les calculs dans l'interface : http://127.0.0.1:8000/salaires/enseignants/")
    print(f"2. Ajustez manuellement les heures si nécessaire pour chaque enseignant")
    print(f"3. Recalculez les états de salaire : http://127.0.0.1:8000/salaires/etats/")
    print(f"4. Les bulletins de salaire afficheront maintenant le calcul détaillé")
    
    print(f"\n🎉 Ajout des heures mensuelles terminé avec succès !")

if __name__ == '__main__':
    ajouter_heures_secondaire()
