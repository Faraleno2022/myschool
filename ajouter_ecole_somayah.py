#!/usr/bin/env python
"""
Script pour ajouter l'École Moderne myschool - Somayah
avec ses grilles tarifaires spécifiques
"""
import os
import sys
import django
from decimal import Decimal

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.contrib.auth.models import User
from eleves.models import Ecole, Classe, GrilleTarifaire

def ajouter_ecole_somayah():
    """Ajouter l'école de Somayah"""
    print("🏫 Ajout de l'École Moderne myschool - Somayah...")
    
    ecole_somayah, created = Ecole.objects.get_or_create(
        nom="École Moderne myschool - Somayah",
        defaults={
            'adresse': "Somayah, Conakry, Guinée",
            'telephone': "+22462200001",
            'email': "somayah@ecole-hadja-kanfing.gn",
            'directeur': "Directeur de l'École - Somayah"
        }
    )
    
    if created:
        print(f"✅ École créée: {ecole_somayah.nom}")
    else:
        print(f"ℹ️  École existante: {ecole_somayah.nom}")
    
    return ecole_somayah

def ajouter_classes_somayah(ecole):
    """Ajouter les classes pour l'école de Somayah"""
    print("📚 Ajout des classes pour Somayah...")
    
    classes_data = [
        # Garderie et Maternelle
        ('GARDERIE', 'Garderie', 'GARDERIE'),
        ('MATERNELLE', 'Maternelle', 'MATERNELLE'),
        
        # Primaire
        ('PRIMAIRE_1', 'Primaire 1ère année', 'PRIMAIRE_1'),
        ('PRIMAIRE_2', 'Primaire 2ème année', 'PRIMAIRE_2'),
        ('PRIMAIRE_3', 'Primaire 3ème année', 'PRIMAIRE_3'),
        ('PRIMAIRE_4', 'Primaire 4ème année', 'PRIMAIRE_4'),
        ('PRIMAIRE_5', 'Primaire 5ème année', 'PRIMAIRE_5'),
        ('PRIMAIRE_6', 'Primaire 6ème année', 'PRIMAIRE_6'),
        
        # Collège
        ('COLLEGE_7', 'Collège 7ème année', 'COLLEGE_7'),
        ('COLLEGE_8', 'Collège 8ème année', 'COLLEGE_8'),
        ('COLLEGE_9', 'Collège 9ème année', 'COLLEGE_9'),
        ('COLLEGE_10', 'Collège 10ème année', 'COLLEGE_10'),
        
        # Lycée
        ('LYCEE_11', 'Lycée 11ème année', 'LYCEE_11'),
        ('LYCEE_12', 'Lycée 12ème année', 'LYCEE_12'),
        ('TERMINALE', 'Terminale', 'TERMINALE'),
    ]
    
    classes_creees = []
    for code, nom, niveau in classes_data:
        classe, created = Classe.objects.get_or_create(
            ecole=ecole,
            nom=nom,
            defaults={
                'niveau': niveau,
                'annee_scolaire': '2024-2025'
            }
        )
        
        if created:
            print(f"✅ Classe créée: {classe.nom} ({classe.niveau})")
        else:
            print(f"ℹ️  Classe existante: {classe.nom}")
        
        classes_creees.append(classe)
    
    return classes_creees

def ajouter_grilles_tarifaires_somayah(ecole):
    """Ajouter les grilles tarifaires spécifiques à Somayah"""
    print("💰 Ajout des grilles tarifaires pour Somayah...")
    
    # Grilles tarifaires selon le tableau fourni
    grilles_data = [
        # (niveau, frais_inscription, tranche_1, tranche_2, tranche_3, total)
        ('MATERNELLE', Decimal('0'), Decimal('650000'), Decimal('500000'), Decimal('350000')),  # Total: 1,500,000
        
        # Primaire (1ère - 2ème - 3ème - 4ème - 5ème) - même tarif
        ('PRIMAIRE_1', Decimal('0'), Decimal('560000'), Decimal('460000'), Decimal('330000')),  # Total: 1,350,000
        ('PRIMAIRE_2', Decimal('0'), Decimal('560000'), Decimal('460000'), Decimal('330000')),
        ('PRIMAIRE_3', Decimal('0'), Decimal('560000'), Decimal('460000'), Decimal('330000')),
        ('PRIMAIRE_4', Decimal('0'), Decimal('560000'), Decimal('460000'), Decimal('330000')),
        ('PRIMAIRE_5', Decimal('0'), Decimal('560000'), Decimal('460000'), Decimal('330000')),
        
        # Primaire 6ème - tarif spécial
        ('PRIMAIRE_6', Decimal('0'), Decimal('710000'), Decimal('610000'), Decimal('380000')),  # Total: 1,700,000
        
        # Collège (7ème - 8ème - 9ème) - même tarif
        ('COLLEGE_7', Decimal('0'), Decimal('660000'), Decimal('660000'), Decimal('300000')),  # Total: 1,620,000
        ('COLLEGE_8', Decimal('0'), Decimal('660000'), Decimal('660000'), Decimal('300000')),
        ('COLLEGE_9', Decimal('0'), Decimal('660000'), Decimal('660000'), Decimal('300000')),
        
        # Collège 10ème - tarif spécial
        ('COLLEGE_10', Decimal('0'), Decimal('710000'), Decimal('610000'), Decimal('480000')),  # Total: 1,800,000
        
        # Lycée (11ème - 12ème) - même tarif
        ('LYCEE_11', Decimal('0'), Decimal('760000'), Decimal('590000'), Decimal('360000')),  # Total: 1,710,000
        ('LYCEE_12', Decimal('0'), Decimal('760000'), Decimal('590000'), Decimal('360000')),
        ('TERMINALE', Decimal('0'), Decimal('760000'), Decimal('590000'), Decimal('360000')),  # Même que 12ème
    ]
    
    grilles_creees = []
    for niveau, inscription, tranche1, tranche2, tranche3 in grilles_data:
        grille, created = GrilleTarifaire.objects.get_or_create(
            ecole=ecole,
            niveau=niveau,
            annee_scolaire='2024-2025',
            defaults={
                'frais_inscription': inscription,
                'tranche_1': tranche1,
                'tranche_2': tranche2,
                'tranche_3': tranche3,
                'periode_1': "À l'inscription",
                'periode_2': 'Début janvier',
                'periode_3': 'Début mars'
            }
        )
        
        total = tranche1 + tranche2 + tranche3
        if created:
            print(f"✅ Grille tarifaire créée: {niveau} - Total: {total:,.0f} GNF")
        else:
            print(f"ℹ️  Grille tarifaire existante: {niveau}")
        
        grilles_creees.append(grille)
    
    return grilles_creees

def main():
    """Fonction principale"""
    print("🚀 Ajout de l'École Moderne myschool - Somayah")
    print("=" * 80)
    
    try:
        # Ajouter l'école de Somayah
        ecole_somayah = ajouter_ecole_somayah()
        
        # Ajouter les classes
        classes = ajouter_classes_somayah(ecole_somayah)
        
        # Ajouter les grilles tarifaires
        grilles = ajouter_grilles_tarifaires_somayah(ecole_somayah)
        
        print("\n" + "=" * 80)
        print("✅ Ajout terminé avec succès !")
        print(f"📊 Résumé:")
        print(f"   - École Somayah ajoutée")
        print(f"   - {len(classes)} classes créées")
        print(f"   - {len(grilles)} grilles tarifaires configurées")
        
        # Afficher un résumé des tarifs
        print(f"\n📋 Résumé des tarifs Somayah (2024-2025):")
        print(f"   - Maternelle: 1,500,000 GNF")
        print(f"   - Primaire (1ère-5ème): 1,350,000 GNF")
        print(f"   - Primaire (6ème): 1,700,000 GNF")
        print(f"   - Collège (7ème-9ème): 1,620,000 GNF")
        print(f"   - Collège (10ème): 1,800,000 GNF")
        print(f"   - Lycée (11ème-12ème): 1,710,000 GNF")
        
        print(f"\n🎓 L'école de Somayah est maintenant configurée !")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
