#!/usr/bin/env python
"""
Script simple pour créer des données de test via Django management command
Usage: python manage.py shell < create_test_data.py
"""

from django.contrib.auth.models import User
from eleves.models import Ecole, Classe, Eleve, Responsable, GrilleTarifaire
from paiements.models import TypePaiement, ModePaiement, Paiement, EcheancierPaiement
from depenses.models import CategorieDepense, Fournisseur, Depense
from salaires.models import Enseignant
from datetime import date, timedelta
from decimal import Decimal
import random

print("🚀 Création de données de test...")

# 1. Créer admin si n'existe pas
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
    print("✅ Admin créé")

# 2. Types et modes de paiement
types_paiement = [
    'Frais d\'inscription',
    'Scolarité - 1ère tranche',
    'Scolarité - 2ème tranche', 
    'Scolarité - 3ème tranche'
]

for nom in types_paiement:
    TypePaiement.objects.get_or_create(nom=nom)

modes_paiement = ['Espèces', 'Mobile Money', 'Virement bancaire']
for nom in modes_paiement:
    ModePaiement.objects.get_or_create(nom=nom)

print("✅ Types et modes de paiement créés")

# 3. Catégories de dépenses
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

print("✅ Catégories de dépenses créées")

# 4. Fournisseurs
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

print("✅ Fournisseurs créés")

# 5. Créer quelques responsables
prenoms = ['Mamadou', 'Aminata', 'Ibrahima', 'Fatoumata', 'Ousmane', 'Mariama']
noms = ['Diallo', 'Barry', 'Bah', 'Sow', 'Camara', 'Touré']

responsables_crees = []
for i in range(20):
    responsable = Responsable.objects.create(
        nom=random.choice(noms),
        prenom=random.choice(prenoms),
        telephone=f"+224 {random.randint(600000000, 699999999)}",
        adresse=f"Quartier {random.choice(['Sonfonia', 'Somayah'])}, Conakry"
    )
    responsables_crees.append(responsable)

print(f"✅ {len(responsables_crees)} responsables créés")

# 6. Créer quelques élèves pour les classes existantes
compteur_matricule = 1
eleves_crees = 0

for classe in Classe.objects.all()[:5]:  # Limiter à 5 classes pour éviter trop de données
    for i in range(5):  # 5 élèves par classe
        sexe = random.choice(['M', 'F'])
        prenom = random.choice(prenoms)
        nom = random.choice(noms)
        
        # Générer matricule unique
        matricule = f"{classe.ecole.id}{classe.niveau[:2]}{compteur_matricule:05d}"
        while Eleve.objects.filter(matricule=matricule).exists():
            compteur_matricule += 1
            matricule = f"{classe.ecole.id}{classe.niveau[:2]}{compteur_matricule:05d}"
        
        age = {'GARDERIE': 3, 'MATERNELLE': 5, 'CP': 6, 'CE1': 7, 'CE2': 8, 'CM1': 9, 'CM2': 10}.get(classe.niveau, 10)
        date_naissance = date.today() - timedelta(days=age * 365)
        
        eleve = Eleve.objects.create(
            nom=nom,
            prenom=prenom,
            sexe=sexe,
            date_naissance=date_naissance,
            lieu_naissance="Conakry, Guinée",
            classe=classe,
            responsable_principal=random.choice(responsables_crees),
            date_inscription=date(2024, 9, random.randint(1, 30)),
            matricule=matricule,
            statut='ACTIF'
        )
        
        # Créer échéancier pour cet élève
        grille = GrilleTarifaire.objects.filter(
            ecole=classe.ecole,
            niveau=classe.niveau
        ).first()
        
        if grille:
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
            
            # 80% payent l'inscription
            if random.random() < 0.8:
                type_inscription = TypePaiement.objects.filter(nom__icontains='inscription').first()
                mode_especes = ModePaiement.objects.first()
                
                if type_inscription and mode_especes:
                    # Générer numéro de reçu unique
                    numero_recu = f"REC-{random.randint(10000, 99999)}-{eleve.id}"
                    while Paiement.objects.filter(numero_recu=numero_recu).exists():
                        numero_recu = f"REC-{random.randint(10000, 99999)}-{eleve.id}"
                    
                    Paiement.objects.create(
                        eleve=eleve,
                        type_paiement=type_inscription,
                        mode_paiement=mode_especes,
                        montant=grille.frais_inscription,
                        date_paiement=eleve.date_inscription,
                        numero_recu=numero_recu,
                        statut='VALIDE'
                    )
                    echeancier.frais_inscription_paye = grille.frais_inscription
                    echeancier.save()
        
        eleves_crees += 1
        compteur_matricule += 1

print(f"✅ {eleves_crees} élèves créés avec échéanciers et paiements")

# 7. Créer quelques dépenses
categories_list = list(CategorieDepense.objects.all())
fournisseurs_list = list(Fournisseur.objects.all())

if categories_list and fournisseurs_list:
    for i in range(10):
        Depense.objects.create(
            numero_facture=f"FACT-{1000+i}",
            categorie=random.choice(categories_list),
            fournisseur=random.choice(fournisseurs_list),
            libelle=f"Dépense test {i+1}",
            type_depense='FONCTIONNEMENT',
            montant_ht=Decimal(str(random.randint(50000, 500000))),
            taux_tva=Decimal('18'),
            date_facture=date.today() - timedelta(days=random.randint(1, 60)),
            date_echeance=date.today() + timedelta(days=30),
            statut='VALIDEE'
        )

print("✅ 10 dépenses créées")

# 8. Créer quelques enseignants
enseignants_data = [
    ('DIALLO', 'Mamadou', 'SECONDAIRE'),
    ('BARRY', 'Fatoumata', 'PRIMAIRE'),
    ('CAMARA', 'Ibrahima', 'MATERNELLE')
]

for nom, prenoms, type_ens in enseignants_data:
    for ecole in Ecole.objects.all():
        Enseignant.objects.get_or_create(
            nom=nom,
            prenoms=prenoms,
            ecole=ecole,
            defaults={
                'type_enseignant': type_ens,
                'salaire_fixe': Decimal('800000'),
                'date_embauche': date(2024, 9, 1),
                'statut': 'ACTIF'
            }
        )

print("✅ Enseignants créés")

print("\n🎉 DONNÉES DE TEST CRÉÉES AVEC SUCCÈS!")
print(f"📊 Résumé:")
print(f"   👥 Utilisateurs: {User.objects.count()}")
print(f"   🏫 Écoles: {Ecole.objects.count()}")
print(f"   📚 Classes: {Classe.objects.count()}")
print(f"   👨‍🎓 Élèves: {Eleve.objects.count()}")
print(f"   👨‍👩‍👧‍👦 Responsables: {Responsable.objects.count()}")
print(f"   💰 Paiements: {Paiement.objects.count()}")
print(f"   💸 Dépenses: {Depense.objects.count()}")
print(f"   👨‍🏫 Enseignants: {Enseignant.objects.count()}")
