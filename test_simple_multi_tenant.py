#!/usr/bin/env python
"""
Test simple et rapide du système multi-tenant
"""
import os
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

import django
django.setup()

from django.contrib.auth.models import User
from eleves.models import Ecole
from utilisateurs.models import Profil
from inscription_ecoles.models import DemandeInscriptionEcole, ConfigurationEcole


def test_system():
    """Test rapide du système"""
    print("🧪 Test rapide du système multi-tenant...\n")
    
    results = []
    
    # Test 1: Modèles de base
    try:
        ecoles_count = Ecole.objects.count()
        users_count = User.objects.count()
        profils_count = Profil.objects.count()
        
        print(f"✅ Modèles fonctionnels:")
        print(f"   - Écoles: {ecoles_count}")
        print(f"   - Utilisateurs: {users_count}")
        print(f"   - Profils: {profils_count}")
        results.append(True)
    except Exception as e:
        print(f"❌ Erreur modèles: {e}")
        results.append(False)
    
    # Test 2: Super-utilisateur
    try:
        admin_exists = User.objects.filter(is_superuser=True).exists()
        if admin_exists:
            admin = User.objects.filter(is_superuser=True).first()
            print(f"✅ Super-admin: {admin.username}")
            results.append(True)
        else:
            print("❌ Aucun super-utilisateur trouvé")
            results.append(False)
    except Exception as e:
        print(f"❌ Erreur super-admin: {e}")
        results.append(False)
    
    # Test 3: Écoles actives
    try:
        ecoles_actives = Ecole.objects.filter(statut='ACTIVE')
        print(f"✅ Écoles actives: {ecoles_actives.count()}")
        for ecole in ecoles_actives[:3]:
            print(f"   - {ecole.nom} ({ecole.slug})")
        results.append(True)
    except Exception as e:
        print(f"❌ Erreur écoles: {e}")
        results.append(False)
    
    # Test 4: Configuration multi-tenant
    try:
        configs_count = ConfigurationEcole.objects.count()
        demandes_count = DemandeInscriptionEcole.objects.count()
        
        print(f"✅ Configuration multi-tenant:")
        print(f"   - Configurations: {configs_count}")
        print(f"   - Demandes d'inscription: {demandes_count}")
        results.append(True)
    except Exception as e:
        print(f"❌ Erreur configuration: {e}")
        results.append(False)
    
    # Test 5: Profils utilisateurs
    try:
        profils_avec_ecole = Profil.objects.filter(ecole__isnull=False).count()
        profils_sans_ecole = Profil.objects.filter(ecole__isnull=True).count()
        
        print(f"✅ Profils utilisateurs:")
        print(f"   - Avec école: {profils_avec_ecole}")
        print(f"   - Sans école: {profils_sans_ecole}")
        
        if profils_sans_ecole > 0:
            print("   ⚠️  Certains utilisateurs n'ont pas d'école assignée")
        
        results.append(True)
    except Exception as e:
        print(f"❌ Erreur profils: {e}")
        results.append(False)
    
    # Résumé
    success_count = sum(results)
    total_tests = len(results)
    
    print(f"\n📊 Résultats: {success_count}/{total_tests} tests réussis")
    
    if success_count == total_tests:
        print("🎉 Système multi-tenant opérationnel!")
        print("\n📋 Actions recommandées:")
        print("1. Accéder à l'interface: http://127.0.0.1:8001/")
        print("2. Se connecter en admin: http://127.0.0.1:8001/admin/")
        print("3. Tester l'inscription d'école: http://127.0.0.1:8001/ecole/inscription/")
        return True
    else:
        print("⚠️  Certains composants nécessitent attention")
        return False


def main():
    """Point d'entrée"""
    try:
        success = test_system()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur critique: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
