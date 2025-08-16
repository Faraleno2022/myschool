#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.db import transaction
from eleves.models import Eleve, Responsable, Classe, HistoriqueEleve, Ecole, GrilleTarifaire
from paiements.models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement, RemiseReduction, PaiementRemise
from depenses.models import Depense, CategorieDepense, Fournisseur
from salaires.models import Enseignant, AffectationClasse, EtatSalaire, PeriodeSalaire, DetailHeuresClasse
from utilisateurs.models import JournalActivite, Profil
from django.contrib.auth.models import User

def reset_all_data():
    """Supprime toutes les données de la base de données"""
    
    print("Suppression de toutes les donnees...")
    
    try:
        with transaction.atomic():
            # 1. Journaux d'activite
            count = JournalActivite.objects.count()
            JournalActivite.objects.all().delete()
            print(f"Journaux d'activite supprimes: {count}")
            
            # 2. Donnees de paiements
            count = PaiementRemise.objects.count()
            PaiementRemise.objects.all().delete()
            print(f"Remises paiements supprimees: {count}")
            
            count = Paiement.objects.count()
            Paiement.objects.all().delete()
            print(f"Paiements supprimes: {count}")
            
            count = EcheancierPaiement.objects.count()
            EcheancierPaiement.objects.all().delete()
            print(f"Echeanciers supprimes: {count}")
            
            count = RemiseReduction.objects.count()
            RemiseReduction.objects.all().delete()
            print(f"Remises supprimees: {count}")
            
            # 3. Donnees de salaires
            count = DetailHeuresClasse.objects.count()
            DetailHeuresClasse.objects.all().delete()
            print(f"Details heures supprimes: {count}")
            
            count = EtatSalaire.objects.count()
            EtatSalaire.objects.all().delete()
            print(f"Etats salaires supprimes: {count}")
            
            count = PeriodeSalaire.objects.count()
            PeriodeSalaire.objects.all().delete()
            print(f"Periodes salaires supprimees: {count}")
            
            count = AffectationClasse.objects.count()
            AffectationClasse.objects.all().delete()
            print(f"Affectations supprimees: {count}")
            
            count = Enseignant.objects.count()
            Enseignant.objects.all().delete()
            print(f"Enseignants supprimes: {count}")
            
            # 4. Donnees de depenses
            count = Depense.objects.count()
            Depense.objects.all().delete()
            print(f"Depenses supprimees: {count}")
            
            count = Fournisseur.objects.count()
            Fournisseur.objects.all().delete()
            print(f"Fournisseurs supprimes: {count}")
            
            count = CategorieDepense.objects.count()
            CategorieDepense.objects.all().delete()
            print(f"Categories depenses supprimees: {count}")
            
            # 5. Donnees d'eleves
            count = HistoriqueEleve.objects.count()
            HistoriqueEleve.objects.all().delete()
            print(f"Historiques eleves supprimes: {count}")
            
            count = Eleve.objects.count()
            Eleve.objects.all().delete()
            print(f"Eleves supprimes: {count}")
            
            count = Responsable.objects.count()
            Responsable.objects.all().delete()
            print(f"Responsables supprimes: {count}")
            
            # 6. Profils utilisateurs AVANT ecoles (fix contrainte FK)
            count = Profil.objects.filter(user__is_superuser=False).count()
            Profil.objects.filter(user__is_superuser=False).delete()
            print(f"Profils utilisateurs supprimes: {count}")
            
            count = User.objects.filter(is_superuser=False).count()
            User.objects.filter(is_superuser=False).delete()
            print(f"Utilisateurs non-admin supprimes: {count}")
            
            # 7. Donnees d'ecoles (apres profils)
            count = Classe.objects.count()
            Classe.objects.all().delete()
            print(f"Classes supprimees: {count}")
            
            count = GrilleTarifaire.objects.count()
            GrilleTarifaire.objects.all().delete()
            print(f"Grilles tarifaires supprimees: {count}")
            
            count = Ecole.objects.count()
            Ecole.objects.all().delete()
            print(f"Ecoles supprimees: {count}")
            
        print("Suppression terminee avec succes !")
        print("Base de donnees reinitialisee.")
        
    except Exception as e:
        print(f"Erreur lors de la suppression: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    reset_all_data()
