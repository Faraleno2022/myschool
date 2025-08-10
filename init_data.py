#!/usr/bin/env python
"""
Script d'initialisation des données de base pour l'École Moderne HADJA KANFING DIANÉ
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
from paiements.models import TypePaiement, ModePaiement
from depenses.models import CategorieDepense
from utilisateurs.models import ParametreSysteme

def init_ecoles():
    """Initialiser les écoles"""
    print("🏫 Initialisation des écoles...")
    
    ecole, created = Ecole.objects.get_or_create(
        nom="École Moderne HADJA KANFING DIANÉ",
        defaults={
            'adresse': "Conakry, Guinée",
            'telephone': "+22462200000",
            'email': "contact@ecole-hadja-kanfing.gn",
            'directeur': "Directeur de l'École"
        }
    )
    
    if created:
        print(f"✅ École créée: {ecole.nom}")
    else:
        print(f"ℹ️  École existante: {ecole.nom}")
    
    return ecole

def init_classes(ecole):
    """Initialiser les classes"""
    print("📚 Initialisation des classes...")
    
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

def init_grilles_tarifaires(ecole):
    """Initialiser les grilles tarifaires"""
    print("💰 Initialisation des grilles tarifaires...")
    
    # Niveaux avec leurs tarifs respectifs
    niveaux_tarifs = [
        ('GARDERIE', Decimal('400000'), Decimal('800000'), Decimal('800000')),
        ('MATERNELLE', Decimal('500000'), Decimal('900000'), Decimal('900000')),
        ('PRIMAIRE_1', Decimal('600000'), Decimal('1000000'), Decimal('1000000')),
        ('PRIMAIRE_2', Decimal('600000'), Decimal('1000000'), Decimal('1000000')),
        ('PRIMAIRE_3', Decimal('650000'), Decimal('1100000'), Decimal('1100000')),
        ('PRIMAIRE_4', Decimal('650000'), Decimal('1100000'), Decimal('1100000')),
        ('PRIMAIRE_5', Decimal('700000'), Decimal('1200000'), Decimal('1200000')),
        ('PRIMAIRE_6', Decimal('700000'), Decimal('1200000'), Decimal('1200000')),
        ('COLLEGE_7', Decimal('800000'), Decimal('1400000'), Decimal('1400000')),
        ('COLLEGE_8', Decimal('800000'), Decimal('1400000'), Decimal('1400000')),
        ('COLLEGE_9', Decimal('900000'), Decimal('1500000'), Decimal('1500000')),
        ('COLLEGE_10', Decimal('900000'), Decimal('1500000'), Decimal('1500000')),
        ('LYCEE_11', Decimal('1000000'), Decimal('1600000'), Decimal('1600000')),
        ('LYCEE_12', Decimal('1000000'), Decimal('1600000'), Decimal('1600000')),
        ('TERMINALE', Decimal('1100000'), Decimal('1700000'), Decimal('1700000')),
    ]
    
    grilles_creees = []
    for niveau, inscription, tranche1, tranche2 in niveaux_tarifs:
        grille, created = GrilleTarifaire.objects.get_or_create(
            ecole=ecole,
            niveau=niveau,
            annee_scolaire='2024-2025',
            defaults={
                'frais_inscription': inscription,
                'tranche_1': tranche1,
                'tranche_2': tranche2,
                'tranche_3': tranche2,  # Même montant pour les tranches 2 et 3
                'periode_1': "À l'inscription",
                'periode_2': 'Début janvier',
                'periode_3': 'Début mars'
            }
        )
        
        if created:
            print(f"✅ Grille tarifaire créée: {niveau} - {inscription} GNF")
        else:
            print(f"ℹ️  Grille tarifaire existante: {niveau}")
        
        grilles_creees.append(grille)
    
    return grilles_creees

def init_types_paiements():
    """Initialiser les types de paiements"""
    print("💳 Initialisation des types de paiements...")
    
    types_data = [
        ('Frais d\'inscription', 'Paiement des frais d\'inscription annuels'),
        ('Scolarité 1ère tranche', 'Frais de scolarité de la première tranche'),
        ('Scolarité 2ème tranche', 'Frais de scolarité de la deuxième tranche'),
        ('Scolarité 3ème tranche', 'Frais de scolarité de la troisième tranche'),
        ('Transport scolaire', 'Frais de transport scolaire'),
        ('Cantine scolaire', 'Frais de restauration scolaire'),
        ('Frais d\'examen', 'Frais liés aux examens et évaluations'),
        ('Fournitures scolaires', 'Achat de fournitures scolaires'),
        ('Uniforme scolaire', 'Achat d\'uniformes scolaires'),
        ('Activités extra-scolaires', 'Frais pour activités sportives et culturelles'),
    ]
    
    for nom, description in types_data:
        type_paiement, created = TypePaiement.objects.get_or_create(
            nom=nom,
            defaults={
                'description': description,
                'actif': True
            }
        )
        
        if created:
            print(f"✅ Type de paiement créé: {type_paiement.nom}")
        else:
            print(f"ℹ️  Type de paiement existant: {type_paiement.nom}")

def init_modes_paiements():
    """Initialiser les modes de paiements"""
    print("💰 Initialisation des modes de paiements...")
    
    modes_data = [
        ('Espèces', 'Paiement en espèces (GNF)', True, Decimal('0')),
        ('Chèque', 'Paiement par chèque bancaire', True, Decimal('0')),
        ('Virement bancaire', 'Virement sur compte bancaire de l\'ecole', True, Decimal('0')),
        ('Mobile Money', 'Paiement via Orange Money, MTN Money, etc.', True, Decimal('5000')),  # Frais de 5000 GNF
        ('Carte bancaire', 'Paiement par carte bancaire', False, Decimal('0')),  # Pas encore disponible
        ('Crédit', 'Paiement différé ou échelonné', True, Decimal('0')),
    ]
    
    for nom, description, actif, frais in modes_data:
        mode_paiement, created = ModePaiement.objects.get_or_create(
            nom=nom,
            defaults={
                'description': description,
                'actif': actif,
                'frais_supplementaires': frais
            }
        )
        
        if created:
            print(f"✅ Mode de paiement créé: {mode_paiement.nom}")
        else:
            print(f"ℹ️  Mode de paiement existant: {mode_paiement.nom}")

def init_categories_depenses():
    """Initialiser les catégories de dépenses"""
    print("📊 Initialisation des catégories de dépenses...")
    
    categories_data = [
        ('SALAIRES', 'Salaires et charges', 'Rémunération du personnel et charges sociales'),
        ('FOURNITURES', 'Fournitures pédagogiques', 'Matériel pédagogique et fournitures scolaires'),
        ('MAINTENANCE', 'Maintenance et réparations', 'Entretien des bâtiments et équipements'),
        ('UTILITIES', 'Services publics', 'Électricité, eau, internet, téléphone'),
        ('TRANSPORT', 'Transport', 'Frais de transport et carburant'),
        ('FORMATION', 'Formation du personnel', 'Formation continue des enseignants'),
        ('EQUIPEMENTS', 'Équipements', 'Achat d\'équipements et mobilier'),
        ('ADMIN', 'Frais administratifs', 'Frais de gestion et administration'),
        ('SECURITE', 'Sécurité', 'Services de sécurité et surveillance'),
        ('ALIMENT', 'Alimentation', 'Frais de cantine et restauration'),
    ]
    
    for code, nom, description in categories_data:
        categorie, created = CategorieDepense.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'description': description,
                'actif': True
            }
        )
        
        
        if created:
            print(f"✅ Catégorie de dépense créée: {categorie.nom}")
        else:
            print(f"ℹ️  Catégorie de dépense existante: {categorie.nom}")

def init_parametres_systeme():
    """Initialiser les paramètres système"""
    print("⚙️  Initialisation des paramètres système...")
    
    parametres_data = [
        ('ANNEE_SCOLAIRE_COURANTE', '2024-2025', 'Année scolaire en cours'),
        ('DEVISE', 'GNF', 'Devise utilisée (Franc Guinéen)'),
        ('LANGUE_DEFAUT', 'fr', 'Langue par défaut de l\'application'),
        ('FUSEAU_HORAIRE', 'Africa/Conakry', 'Fuseau horaire de l\'école'),
        ('EMAIL_NOTIFICATIONS', 'true', 'Activer les notifications par email'),
        ('BACKUP_AUTO', 'true', 'Sauvegarde automatique activée'),
        ('MODE_MAINTENANCE', 'false', 'Mode maintenance de l\'application'),
    ]
    
    for cle, valeur, description in parametres_data:
        parametre, created = ParametreSysteme.objects.get_or_create(
            cle=cle,
            defaults={
                'valeur': valeur,
                'description': description,
                'modifie_par': User.objects.filter(is_superuser=True).first()
            }
        )
        
        if created:
            print(f"✅ Paramètre créé: {parametre.cle} = {parametre.valeur}")
        else:
            print(f"ℹ️  Paramètre existant: {parametre.cle} = {parametre.valeur}")

def main():
    """Fonction principale d'initialisation"""
    print("🚀 Initialisation des données de base pour l'École Moderne HADJA KANFING DIANÉ")
    print("=" * 80)
    
    try:
        # Initialiser les données de base
        ecole = init_ecoles()
        classes = init_classes(ecole)
        grille = init_grilles_tarifaires(ecole)
        init_types_paiements()
        init_modes_paiements()
        init_categories_depenses()
        init_parametres_systeme()
        
        print("\n" + "=" * 80)
        print("✅ Initialisation terminée avec succès !")
        print(f"📊 Résumé:")
        print(f"   - 1 école initialisée")
        print(f"   - {len(classes)} classes créées")
        print(f"   - 1 grille tarifaire configurée")
        print(f"   - Types et modes de paiements configurés")
        print(f"   - Catégories de dépenses configurées")
        print(f"   - Paramètres système configurés")
        print("\n🎓 L'application est prête à être utilisée !")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
