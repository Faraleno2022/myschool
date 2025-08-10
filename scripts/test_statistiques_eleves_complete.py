#!/usr/bin/env python
"""
Script de test complet pour vérifier toutes les statistiques élèves
Teste tous les calculs et affichages de la page statistiques
"""

import os
import sys
import django
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.db.models import Count, Sum, Avg, Q, Case, When, IntegerField
from eleves.models import Eleve, Ecole, Classe, Responsable
from paiements.models import Paiement

def test_statistiques_generales():
    """Test des statistiques générales"""
    print("=" * 60)
    print("🔍 TEST DES STATISTIQUES GÉNÉRALES")
    print("=" * 60)
    
    # Calculs identiques à la vue
    total_eleves = Eleve.objects.count()
    eleves_actifs = Eleve.objects.filter(statut='ACTIF').count()
    eleves_suspendus = Eleve.objects.filter(statut='SUSPENDU').count()
    eleves_exclus = Eleve.objects.filter(statut='EXCLU').count()
    eleves_transferes = Eleve.objects.filter(statut='TRANSFERE').count()
    eleves_diplomes = Eleve.objects.filter(statut='DIPLOME').count()
    
    total_ecoles = Ecole.objects.count()
    total_classes = Classe.objects.count()
    total_responsables = Responsable.objects.count()
    
    print(f"📊 Total élèves: {total_eleves:,}")
    print(f"✅ Élèves actifs: {eleves_actifs:,}")
    print(f"⏸️  Élèves suspendus: {eleves_suspendus:,}")
    print(f"❌ Élèves exclus: {eleves_exclus:,}")
    print(f"🔄 Élèves transférés: {eleves_transferes:,}")
    print(f"🎓 Élèves diplômés: {eleves_diplomes:,}")
    print(f"🏫 Total écoles: {total_ecoles:,}")
    print(f"📚 Total classes: {total_classes:,}")
    print(f"👥 Total responsables: {total_responsables:,}")
    
    return {
        'total_eleves': total_eleves,
        'eleves_actifs': eleves_actifs,
        'eleves_suspendus': eleves_suspendus,
        'eleves_exclus': eleves_exclus,
        'eleves_transferes': eleves_transferes,
        'eleves_diplomes': eleves_diplomes,
        'total_ecoles': total_ecoles,
        'total_classes': total_classes,
        'total_responsables': total_responsables,
    }

def test_statistiques_demographiques():
    """Test des statistiques démographiques"""
    print("\n" + "=" * 60)
    print("👥 TEST DES STATISTIQUES DÉMOGRAPHIQUES")
    print("=" * 60)
    
    # Calculs par sexe
    total_garcons = Eleve.objects.filter(sexe='M').count()
    total_filles = Eleve.objects.filter(sexe='F').count()
    total_eleves = Eleve.objects.count()
    
    pourcentage_garcons = (total_garcons / total_eleves * 100) if total_eleves > 0 else 0
    pourcentage_filles = (total_filles / total_eleves * 100) if total_eleves > 0 else 0
    
    print(f"👦 Total garçons: {total_garcons:,} ({pourcentage_garcons:.1f}%)")
    print(f"👧 Total filles: {total_filles:,} ({pourcentage_filles:.1f}%)")
    
    return {
        'total_garcons': total_garcons,
        'total_filles': total_filles,
        'pourcentage_garcons': pourcentage_garcons,
        'pourcentage_filles': pourcentage_filles,
    }

def test_statistiques_age():
    """Test des statistiques d'âge"""
    print("\n" + "=" * 60)
    print("📅 TEST DES STATISTIQUES D'ÂGE")
    print("=" * 60)
    
    # Calcul des âges
    eleves_avec_age = []
    for eleve in Eleve.objects.filter(date_naissance__isnull=False):
        age = relativedelta(datetime.now().date(), eleve.date_naissance).years
        eleves_avec_age.append(age)
    
    if eleves_avec_age:
        age_moyen = sum(eleves_avec_age) / len(eleves_avec_age)
        age_min = min(eleves_avec_age)
        age_max = max(eleves_avec_age)
        
        # Répartition par tranches d'âge
        moins_10 = sum(1 for age in eleves_avec_age if age < 10)
        de_10_15 = sum(1 for age in eleves_avec_age if 10 <= age < 15)
        de_15_18 = sum(1 for age in eleves_avec_age if 15 <= age < 18)
        plus_18 = sum(1 for age in eleves_avec_age if age >= 18)
        
        print(f"📊 Âge moyen: {age_moyen:.1f} ans")
        print(f"📉 Âge minimum: {age_min} ans")
        print(f"📈 Âge maximum: {age_max} ans")
        print(f"👶 Moins de 10 ans: {moins_10:,}")
        print(f"🧒 10-14 ans: {de_10_15:,}")
        print(f"👦 15-17 ans: {de_15_18:,}")
        print(f"👨 18+ ans: {plus_18:,}")
        
        return {
            'age_moyen': age_moyen,
            'age_min': age_min,
            'age_max': age_max,
            'moins_10': moins_10,
            'de_10_15': de_10_15,
            'de_15_18': de_15_18,
            'plus_18': plus_18,
        }
    else:
        print("⚠️  Aucune donnée d'âge disponible")
        return {}

def test_statistiques_par_ecole():
    """Test des statistiques par école"""
    print("\n" + "=" * 60)
    print("🏫 TEST DES STATISTIQUES PAR ÉCOLE")
    print("=" * 60)
    
    stats_par_ecole = []
    for ecole in Ecole.objects.all():
        eleves_ecole = Eleve.objects.filter(classe__ecole=ecole)
        total_eleves_ecole = eleves_ecole.count()
        eleves_actifs_ecole = eleves_ecole.filter(statut='ACTIF').count()
        garcons_ecole = eleves_ecole.filter(sexe='M').count()
        filles_ecole = eleves_ecole.filter(sexe='F').count()
        classes_ecole = Classe.objects.filter(ecole=ecole).count()
        classes_actives = Classe.objects.filter(ecole=ecole, eleves__statut='ACTIF').distinct().count()
        
        pourcentage_garcons = (garcons_ecole / total_eleves_ecole * 100) if total_eleves_ecole > 0 else 0
        pourcentage_filles = (filles_ecole / total_eleves_ecole * 100) if total_eleves_ecole > 0 else 0
        moyenne_eleves_par_classe = (total_eleves_ecole / classes_ecole) if classes_ecole > 0 else 0
        
        ecole_stats = {
            'nom': ecole.nom,
            'total_eleves': total_eleves_ecole,
            'eleves_actifs': eleves_actifs_ecole,
            'garcons': garcons_ecole,
            'filles': filles_ecole,
            'classes': classes_ecole,
            'classes_actives': classes_actives,
            'pourcentage_garcons': pourcentage_garcons,
            'pourcentage_filles': pourcentage_filles,
            'moyenne_eleves_par_classe': moyenne_eleves_par_classe,
        }
        stats_par_ecole.append(ecole_stats)
        
        print(f"\n🏫 {ecole.nom}:")
        print(f"   📊 Total élèves: {total_eleves_ecole:,}")
        print(f"   ✅ Élèves actifs: {eleves_actifs_ecole:,}")
        print(f"   👦 Garçons: {garcons_ecole:,} ({pourcentage_garcons:.1f}%)")
        print(f"   👧 Filles: {filles_ecole:,} ({pourcentage_filles:.1f}%)")
        print(f"   📚 Classes: {classes_ecole:,} (actives: {classes_actives:,})")
        print(f"   📈 Moyenne élèves/classe: {moyenne_eleves_par_classe:.1f}")
    
    return stats_par_ecole

def test_statistiques_temporelles():
    """Test des statistiques temporelles"""
    print("\n" + "=" * 60)
    print("📅 TEST DES STATISTIQUES TEMPORELLES")
    print("=" * 60)
    
    maintenant = datetime.now()
    
    # Inscriptions récentes
    cette_semaine = Eleve.objects.filter(
        date_inscription__gte=maintenant - timedelta(days=7)
    ).count()
    
    ce_mois = Eleve.objects.filter(
        date_inscription__year=maintenant.year,
        date_inscription__month=maintenant.month
    ).count()
    
    cette_annee = Eleve.objects.filter(
        date_inscription__year=maintenant.year
    ).count()
    
    print(f"📅 Inscriptions cette semaine: {cette_semaine:,}")
    print(f"📅 Inscriptions ce mois: {ce_mois:,}")
    print(f"📅 Inscriptions cette année: {cette_annee:,}")
    
    # Évolution mensuelle (6 derniers mois)
    print(f"\n📈 Évolution mensuelle (6 derniers mois):")
    for i in range(6):
        date_mois = maintenant - relativedelta(months=i)
        inscriptions_mois = Eleve.objects.filter(
            date_inscription__year=date_mois.year,
            date_inscription__month=date_mois.month
        ).count()
        print(f"   {date_mois.strftime('%B %Y')}: {inscriptions_mois:,} inscriptions")
    
    return {
        'cette_semaine': cette_semaine,
        'ce_mois': ce_mois,
        'cette_annee': cette_annee,
    }

def test_statistiques_financieres():
    """Test des statistiques financières"""
    print("\n" + "=" * 60)
    print("💰 TEST DES STATISTIQUES FINANCIÈRES")
    print("=" * 60)
    
    # Élèves avec/sans paiements
    eleves_avec_paiements = Eleve.objects.filter(paiements__isnull=False).distinct().count()
    eleves_sans_paiements = Eleve.objects.filter(paiements__isnull=True).count()
    
    # Statistiques des paiements
    total_paiements = Paiement.objects.count()
    paiements_valides = Paiement.objects.filter(statut='VALIDE').count()
    paiements_en_attente = Paiement.objects.filter(statut='EN_ATTENTE').count()
    
    taux_validation = (paiements_valides / total_paiements * 100) if total_paiements > 0 else 0
    
    print(f"💰 Élèves avec paiements: {eleves_avec_paiements:,}")
    print(f"💸 Élèves sans paiements: {eleves_sans_paiements:,}")
    print(f"📊 Total paiements: {total_paiements:,}")
    print(f"✅ Paiements validés: {paiements_valides:,}")
    print(f"⏳ Paiements en attente: {paiements_en_attente:,}")
    print(f"📈 Taux de validation: {taux_validation:.1f}%")
    
    return {
        'eleves_avec_paiements': eleves_avec_paiements,
        'eleves_sans_paiements': eleves_sans_paiements,
        'total_paiements': total_paiements,
        'paiements_valides': paiements_valides,
        'paiements_en_attente': paiements_en_attente,
        'taux_validation': taux_validation,
    }

def test_indicateurs_performance():
    """Test des indicateurs de performance"""
    print("\n" + "=" * 60)
    print("📊 TEST DES INDICATEURS DE PERFORMANCE")
    print("=" * 60)
    
    total_eleves = Eleve.objects.count()
    eleves_actifs = Eleve.objects.filter(statut='ACTIF').count()
    total_classes = Classe.objects.count()
    total_responsables = Responsable.objects.count()
    
    # Calcul des indicateurs
    taux_activite = (eleves_actifs / total_eleves * 100) if total_eleves > 0 else 0
    taux_retention = 100 - (Eleve.objects.filter(statut__in=['TRANSFERE', 'EXCLU']).count() / total_eleves * 100) if total_eleves > 0 else 0
    ratio_eleves_classe = (total_eleves / total_classes) if total_classes > 0 else 0
    ratio_eleves_responsable = (total_eleves / total_responsables) if total_responsables > 0 else 0
    
    print(f"📈 Taux d'activité: {taux_activite:.1f}%")
    print(f"🎯 Taux de rétention: {taux_retention:.1f}%")
    print(f"👥 Ratio élèves/classe: {ratio_eleves_classe:.1f}")
    print(f"👨‍👩‍👧‍👦 Ratio élèves/responsable: {ratio_eleves_responsable:.1f}")
    
    return {
        'taux_activite': taux_activite,
        'taux_retention': taux_retention,
        'ratio_eleves_classe': ratio_eleves_classe,
        'ratio_eleves_responsable': ratio_eleves_responsable,
    }

def main():
    """Fonction principale de test"""
    print("🚀 DÉBUT DU TEST COMPLET DES STATISTIQUES ÉLÈVES")
    print(f"📅 Date/Heure: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    try:
        # Tests des différentes sections
        stats_generales = test_statistiques_generales()
        stats_demographiques = test_statistiques_demographiques()
        stats_age = test_statistiques_age()
        stats_par_ecole = test_statistiques_par_ecole()
        stats_temporelles = test_statistiques_temporelles()
        stats_financieres = test_statistiques_financieres()
        indicateurs = test_indicateurs_performance()
        
        print("\n" + "=" * 60)
        print("✅ RÉSUMÉ DU TEST")
        print("=" * 60)
        print(f"📊 Total élèves testés: {stats_generales['total_eleves']:,}")
        print(f"🏫 Écoles testées: {stats_generales['total_ecoles']:,}")
        print(f"📚 Classes testées: {stats_generales['total_classes']:,}")
        print(f"💰 Paiements testés: {stats_financieres['total_paiements']:,}")
        
        print(f"\n🎯 INDICATEURS CLÉS:")
        print(f"   ✅ Taux d'activité: {indicateurs['taux_activite']:.1f}%")
        print(f"   🎯 Taux de rétention: {indicateurs['taux_retention']:.1f}%")
        print(f"   👥 Ratio élèves/classe: {indicateurs['ratio_eleves_classe']:.1f}")
        
        print(f"\n✅ TOUS LES TESTS ONT ÉTÉ EXÉCUTÉS AVEC SUCCÈS!")
        print(f"🔗 Accédez à la page: http://127.0.0.1:8000/eleves/statistiques/")
        
    except Exception as e:
        print(f"\n❌ ERREUR LORS DU TEST: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
