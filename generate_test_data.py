#!/usr/bin/env python
"""
Script de génération de données de test complètes pour le système de gestion scolaire
ATTENTION: Ce script est pour les tests locaux uniquement - ne pas committer sur GitHub
"""

import os
import sys
import django
from datetime import datetime, date, timedelta
from decimal import Decimal
import random

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.contrib.auth.models import User
from eleves.models import Ecole, Classe, Eleve, Responsable, GrilleTarifaire
from paiements.models import TypePaiement, ModePaiement, Paiement, EcheancierPaiement
from depenses.models import CategorieDepense, Fournisseur, Depense
from salaires.models import Enseignant, AffectationClasse, PeriodeSalaire, EtatSalaire
from utilisateurs.models import Profil

def main():
    """Fonction principale de génération des données"""
    print("🚀 GÉNÉRATION DE DONNÉES DE TEST COMPLÈTES")
    print("=" * 50)
    
    try:
        # 1. Utilisateurs et profils
        create_users()
        
        # 2. Écoles et classes
        create_schools()
        
        # 3. Grilles tarifaires
        create_tariffs()
        
        # 4. Types et modes de paiement
        create_payment_types()
        
        # 5. Responsables et élèves
        create_students()
        
        # 6. Paiements
        create_payments()
        
        # 7. Catégories et fournisseurs
        create_expense_data()
        
        # 8. Dépenses
        create_expenses()
        
        # 9. Enseignants
        create_teachers()
        
        print("\n🎉 GÉNÉRATION TERMINÉE AVEC SUCCÈS!")
        print_summary()
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()

def create_users():
    """Créer des utilisateurs"""
    print("🔐 Création des utilisateurs...")
    
    # Admin principal
    admin, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@gshadjakanfing.com',
            'first_name': 'Admin',
            'last_name': 'Principal',
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin.set_password('admin123')
        admin.save()
        print("   ✅ Admin créé")

def create_schools():
    """Créer les écoles et classes"""
    print("🏫 Création des écoles et classes...")
    
    # Écoles
    ecoles_data = [
        ('GROUPE SCOLAIRE HADJA KANFING DIANÉ-SONFONIA', 'Sonfonia, Conakry'),
        ('GROUPE SCOLAIRE HADJA KANFING DIANÉ-SOMAYAH', 'Somayah, Conakry')
    ]
    
    for nom, adresse in ecoles_data:
        ecole, created = Ecole.objects.get_or_create(
            nom=nom,
            defaults={
                'adresse': adresse,
                'telephone': '+224 123 456 789',
                'email': f'{nom.split("-")[-1].lower()}@gshadjakanfing.com'
            }
        )
        if created:
            print(f"   📍 École créée: {nom}")
    
    # Classes
    niveaux = ['GARDERIE', 'MATERNELLE', 'CP', 'CE1', 'CE2', 'CM1', 'CM2', '7EME', '8EME', '9EME']
    
    for ecole in Ecole.objects.all():
        for niveau in niveaux:
            classe, created = Classe.objects.get_or_create(
                nom=niveau,
                ecole=ecole,
                niveau=niveau,
                defaults={
                    'annee_scolaire': '2024-2025',
                    'capacite_max': 30
                }
            )

def create_tariffs():
    """Créer les grilles tarifaires"""
    print("💰 Création des grilles tarifaires...")
    
    tarifs = {
        'GARDERIE': (30000, 150000, 150000, 150000),
        'MATERNELLE': (30000, 180000, 180000, 180000),
        'CP': (30000, 200000, 200000, 200000),
        'CE1': (30000, 200000, 200000, 200000),
        'CE2': (30000, 200000, 200000, 200000),
        'CM1': (30000, 220000, 220000, 220000),
        'CM2': (30000, 220000, 220000, 220000),
        '7EME': (30000, 250000, 250000, 250000),
        '8EME': (30000, 250000, 250000, 250000),
        '9EME': (30000, 280000, 280000, 280000),
    }
    
    for ecole in Ecole.objects.all():
        for niveau, (inscription, t1, t2, t3) in tarifs.items():
            GrilleTarifaire.objects.get_or_create(
                ecole=ecole,
                niveau=niveau,
                annee_scolaire='2024-2025',
                defaults={
                    'frais_inscription': Decimal(str(inscription)),
                    'tranche_1': Decimal(str(t1)),
                    'tranche_2': Decimal(str(t2)),
                    'tranche_3': Decimal(str(t3)),
                }
            )

def create_payment_types():
    """Créer les types et modes de paiement"""
    print("💳 Création des types et modes de paiement...")
    
    # Types
    types = [
        'Frais d\'inscription',
        'Scolarité - 1ère tranche',
        'Scolarité - 2ème tranche',
        'Scolarité - 3ème tranche'
    ]
    
    for nom in types:
        TypePaiement.objects.get_or_create(nom=nom)
    
    # Modes
    modes = ['Espèces', 'Mobile Money', 'Virement bancaire']
    for nom in modes:
        ModePaiement.objects.get_or_create(nom=nom)

def create_students():
    """Créer des élèves et responsables"""
    print("👨‍👩‍👧‍👦 Création des élèves et responsables...")
    
    prenoms = ['Mamadou', 'Aminata', 'Ibrahima', 'Fatoumata', 'Ousmane', 'Mariama']
    noms = ['Diallo', 'Barry', 'Bah', 'Sow', 'Camara', 'Touré']
    
    # Créer des responsables
    responsables = []
    for i in range(30):
        responsable = Responsable.objects.create(
            nom=random.choice(noms),
            prenom=random.choice(prenoms),
            telephone=f"+224 {random.randint(600000000, 699999999)}",
            adresse=f"Quartier {random.choice(['Sonfonia', 'Somayah'])}, Conakry"
        )
        responsables.append(responsable)
    
    # Créer des élèves
    compteur_global = 1
    for classe in Classe.objects.all():
        nb_eleves = random.randint(10, 25)
        
        for i in range(nb_eleves):
            sexe = random.choice(['M', 'F'])
            prenom = random.choice(prenoms)
            nom = random.choice(noms)
            
            age = {'GARDERIE': 3, 'MATERNELLE': 5, 'CP': 6, 'CE1': 7, 'CE2': 8, 'CM1': 9, 'CM2': 10, '7EME': 11, '8EME': 12, '9EME': 13}.get(classe.niveau, 10)
            date_naissance = date.today() - timedelta(days=age * 365)
            
            # Générer un matricule unique
            matricule = f"{classe.ecole.id}{classe.niveau[:2]}{compteur_global:05d}"
            
            # Vérifier l'unicité et ajuster si nécessaire
            while Eleve.objects.filter(matricule=matricule).exists():
                compteur_global += 1
                matricule = f"{classe.ecole.id}{classe.niveau[:2]}{compteur_global:05d}"
            
            eleve = Eleve.objects.create(
                nom=nom,
                prenom=prenom,
                sexe=sexe,
                date_naissance=date_naissance,
                lieu_naissance="Conakry, Guinée",
                classe=classe,
                responsable_principal=random.choice(responsables),
                date_inscription=date(2024, 9, random.randint(1, 30)),
                matricule=matricule,
                statut='ACTIF'
            )
            compteur_global += 1

def create_payments():
    """Créer des paiements"""
    print("💰 Création des paiements...")
    
    type_inscription = TypePaiement.objects.filter(nom__icontains='inscription').first()
    type_tranche1 = TypePaiement.objects.filter(nom__icontains='1ère').first()
    mode_especes = ModePaiement.objects.first()
    
    for eleve in Eleve.objects.all():
        grille = GrilleTarifaire.objects.filter(
            ecole=eleve.classe.ecole,
            niveau=eleve.classe.niveau
        ).first()
        
        if grille:
            # Échéancier
            echeancier = EcheancierPaiement.objects.create(
                eleve=eleve,
                annee_scolaire='2024-2025',
                frais_inscription_du=grille.frais_inscription,
                tranche_1_due=grille.tranche_1,
                tranche_2_due=grille.tranche_2,
                tranche_3_due=grille.tranche_3,
                date_echeance_inscription=date(2024, 9, 30),
                date_echeance_tranche_1=date(2024, 12, 31),
                date_echeance_tranche_2=date(2025, 3, 31),
                date_echeance_tranche_3=date(2025, 6, 30),
            )
            
            # Paiements (80% payent l'inscription)
            if random.random() < 0.8:
                Paiement.objects.create(
                    eleve=eleve,
                    type_paiement=type_inscription,
                    mode_paiement=mode_especes,
                    montant=grille.frais_inscription,
                    date_paiement=eleve.date_inscription,
                    statut='VALIDE'
                )
                echeancier.frais_inscription_paye = grille.frais_inscription
                echeancier.save()

def create_expense_data():
    """Créer catégories et fournisseurs"""
    print("🏪 Création des catégories et fournisseurs...")
    
    # Catégories
    categories = [
        ('FOURNITURES', 'Fournitures scolaires'),
        ('MAINTENANCE', 'Maintenance'),
        ('UTILITIES', 'Services publics'),
        ('TRANSPORT', 'Transport')
    ]
    
    for code, nom in categories:
        CategorieDepense.objects.get_or_create(
            code=code,
            defaults={'nom': nom, 'actif': True}
        )
    
    # Fournisseurs
    fournisseurs = [
        ('Librairie Moderne', 'ENTREPRISE'),
        ('Électricité de Guinée', 'ENTREPRISE'),
        ('Garage Central', 'ENTREPRISE')
    ]
    
    for nom, type_f in fournisseurs:
        Fournisseur.objects.get_or_create(
            nom=nom,
            defaults={'type_fournisseur': type_f, 'actif': True}
        )

def create_expenses():
    """Créer des dépenses"""
    print("💸 Création des dépenses...")
    
    categories = list(CategorieDepense.objects.all())
    fournisseurs = list(Fournisseur.objects.all())
    
    for i in range(20):
        if categories and fournisseurs:
            Depense.objects.create(
                numero_facture=f"FACT-{1000+i}",
                categorie=random.choice(categories),
                fournisseur=random.choice(fournisseurs),
                libelle=f"Dépense test {i+1}",
                type_depense='FONCTIONNEMENT',
                montant_ht=Decimal(str(random.randint(50000, 500000))),
                taux_tva=Decimal('18'),
                date_facture=date.today() - timedelta(days=random.randint(1, 60)),
                date_echeance=date.today() + timedelta(days=30),
                statut='VALIDEE'
            )

def create_teachers():
    """Créer des enseignants"""
    print("👨‍🏫 Création des enseignants...")
    
    enseignants_data = [
        ('DIALLO', 'Mamadou', 'SECONDAIRE', 15000, None),
        ('BARRY', 'Fatoumata', 'PRIMAIRE', None, 800000),
        ('CAMARA', 'Ibrahima', 'MATERNELLE', None, 600000)
    ]
    
    for nom, prenoms, type_ens, taux, salaire in enseignants_data:
        for ecole in Ecole.objects.all():
            Enseignant.objects.get_or_create(
                nom=nom,
                prenoms=prenoms,
                ecole=ecole,
                defaults={
                    'type_enseignant': type_ens,
                    'taux_horaire': Decimal(str(taux)) if taux else None,
                    'salaire_fixe': Decimal(str(salaire)) if salaire else None,
                    'heures_mensuelles': Decimal('120') if taux else None,
                    'date_embauche': date(2024, 9, 1),
                    'statut': 'ACTIF'
                }
            )

def print_summary():
    """Afficher un résumé des données créées"""
    print("\n📊 RÉSUMÉ DES DONNÉES CRÉÉES:")
    print(f"   👥 Utilisateurs: {User.objects.count()}")
    print(f"   🏫 Écoles: {Ecole.objects.count()}")
    print(f"   📚 Classes: {Classe.objects.count()}")
    print(f"   👨‍🎓 Élèves: {Eleve.objects.count()}")
    print(f"   👨‍👩‍👧‍👦 Responsables: {Responsable.objects.count()}")
    print(f"   💰 Paiements: {Paiement.objects.count()}")
    print(f"   💸 Dépenses: {Depense.objects.count()}")
    print(f"   👨‍🏫 Enseignants: {Enseignant.objects.count()}")

if __name__ == '__main__':
    main()
