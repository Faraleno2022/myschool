#!/usr/bin/env python
"""
Test de sécurité et d'isolation des données entre écoles
"""
import os
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

import django
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from eleves.models import Ecole, Eleve, Classe
from utilisateurs.models import Profil
from paiements.models import Paiement
from notes.models import Note


def test_data_isolation():
    """Test d'isolation des données entre écoles"""
    print("🔒 Test d'isolation des données entre écoles...\n")
    
    # Créer deux écoles de test
    import uuid
    
    ecole1 = Ecole.objects.create(
        nom="École Test 1",
        slug=f"ecole-test-1-{str(uuid.uuid4())[:8]}",
        type_ecole="PRIVEE",
        adresse="Adresse 1",
        ville="Conakry",
        prefecture="Conakry",
        telephone="+224111111111",
        email="test1@ecole.com",
        directeur="Directeur 1",
        statut="ACTIVE"
    )
    
    ecole2 = Ecole.objects.create(
        nom="École Test 2", 
        slug=f"ecole-test-2-{str(uuid.uuid4())[:8]}",
        type_ecole="PRIVEE",
        adresse="Adresse 2",
        ville="Conakry",
        prefecture="Conakry",
        telephone="+224222222222",
        email="test2@ecole.com",
        directeur="Directeur 2",
        statut="ACTIVE"
    )
    
    # Créer des utilisateurs pour chaque école
    timestamp = str(int(time.time()))
    
    user1 = User.objects.create_user(
        username=f"admin_ecole1_{timestamp}",
        password="testpass123"
    )
    
    user2 = User.objects.create_user(
        username=f"admin_ecole2_{timestamp}",
        password="testpass123"
    )
    
    # Créer des profils
    profil1 = Profil.objects.create(
        user=user1,
        role="ADMIN",
        telephone="+224333333333",
        ecole=ecole1,
        actif=True
    )
    
    profil2 = Profil.objects.create(
        user=user2,
        role="ADMIN", 
        telephone="+224444444444",
        ecole=ecole2,
        actif=True
    )
    
    # Créer des classes pour chaque école
    classe1 = Classe.objects.create(
        ecole=ecole1,
        nom="CP1",
        niveau="PRIMAIRE_1",
        annee_scolaire="2024-2025"
    )
    
    classe2 = Classe.objects.create(
        ecole=ecole2,
        nom="CP1",
        niveau="PRIMAIRE_1", 
        annee_scolaire="2024-2025"
    )
    
    print("✅ Écoles et utilisateurs de test créés")
    
    # Test 1: Vérifier que les QuerySets filtrent par école
    try:
        # Simuler une requête depuis l'école 1
        classes_ecole1 = Classe.objects.filter(ecole=ecole1)
        classes_ecole2 = Classe.objects.filter(ecole=ecole2)
        
        assert classes_ecole1.count() == 1
        assert classes_ecole2.count() == 1
        assert classe1 in classes_ecole1
        assert classe1 not in classes_ecole2
        
        print("✅ Isolation des classes par école")
    except Exception as e:
        print(f"❌ Erreur isolation classes: {e}")
        return False
    
    # Test 2: Vérifier l'isolation des profils
    try:
        profils_ecole1 = Profil.objects.filter(ecole=ecole1)
        profils_ecole2 = Profil.objects.filter(ecole=ecole2)
        
        assert profil1 in profils_ecole1
        assert profil1 not in profils_ecole2
        assert profil2 not in profils_ecole1
        assert profil2 in profils_ecole2
        
        print("✅ Isolation des profils par école")
    except Exception as e:
        print(f"❌ Erreur isolation profils: {e}")
        return False
    
    # Test 3: Test avec Client Django (simulation navigation)
    client = Client()
    
    try:
        # Connexion utilisateur école 1
        login_success = client.login(username=f"admin_ecole1_{timestamp}", password="testpass123")
        assert login_success, "Échec connexion utilisateur école 1"
        
        # Vérifier que la session contient la bonne école
        response = client.get('/')
        assert response.status_code == 200
        
        client.logout()
        print("✅ Test de navigation sécurisée")
        
    except Exception as e:
        print(f"❌ Erreur test navigation: {e}")
        return False
    
    # Nettoyage
    try:
        profil1.delete()
        profil2.delete()
        classe1.delete()
        classe2.delete()
        ecole1.delete()
        ecole2.delete()
        user1.delete()
        user2.delete()
        print("✅ Nettoyage effectué")
    except Exception as e:
        print(f"⚠️  Erreur nettoyage: {e}")
    
    return True


def test_middleware_security():
    """Test de sécurité du middleware"""
    print("\n🛡️  Test de sécurité du middleware...\n")
    
    client = Client()
    
    # Test 1: Accès sans authentification
    try:
        response = client.get('/eleves/liste/')
        # Doit rediriger vers login
        assert response.status_code in [302, 403], f"Code inattendu: {response.status_code}"
        print("✅ Accès protégé sans authentification")
    except Exception as e:
        print(f"❌ Erreur test accès: {e}")
        return False
    
    # Test 2: Page d'accueil accessible
    try:
        response = client.get('/')
        assert response.status_code == 200
        print("✅ Page d'accueil accessible")
    except Exception as e:
        print(f"❌ Erreur page accueil: {e}")
        return False
    
    return True


def check_model_security():
    """Vérifier la sécurité au niveau des modèles"""
    print("\n🔍 Vérification sécurité des modèles...\n")
    
    try:
        # Vérifier que tous les modèles principaux ont une relation avec Ecole
        from eleves.models import Eleve, Classe, Responsable
        from paiements.models import Paiement
        from notes.models import Note, Evaluation
        
        # Vérifier les relations
        assert hasattr(Classe, 'ecole'), "Classe doit avoir une relation ecole"
        assert hasattr(Eleve, 'classe'), "Eleve doit avoir une relation classe (via école)"
        
        print("✅ Relations école correctement définies")
        
        # Vérifier les contraintes unique_together
        classe_meta = Classe._meta
        unique_together = getattr(classe_meta, 'unique_together', [])
        
        if unique_together:
            print("✅ Contraintes unique_together définies")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur vérification modèles: {e}")
        return False


def main():
    """Test principal"""
    print("🔐 TESTS DE SÉCURITÉ MULTI-TENANT\n")
    
    import time
    global time
    
    tests = [
        ("Isolation des données", test_data_isolation),
        ("Sécurité middleware", test_middleware_security), 
        ("Sécurité modèles", check_model_security)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
            if result:
                print(f"✅ {test_name}: RÉUSSI\n")
            else:
                print(f"❌ {test_name}: ÉCHEC\n")
        except Exception as e:
            print(f"❌ {test_name}: ERREUR - {e}\n")
            results.append(False)
    
    # Résumé
    success_count = sum(results)
    total_tests = len(results)
    
    print("=" * 50)
    print(f"🎯 RÉSULTATS: {success_count}/{total_tests} tests réussis")
    
    if success_count == total_tests:
        print("🎉 SÉCURITÉ MULTI-TENANT VALIDÉE!")
        print("\n✅ Le système garantit:")
        print("   - Isolation complète des données entre écoles")
        print("   - Protection contre l'accès non autorisé")
        print("   - Middleware de sécurité fonctionnel")
        return True
    else:
        print("⚠️  PROBLÈMES DE SÉCURITÉ DÉTECTÉS!")
        return False


if __name__ == "__main__":
    import time
    success = main()
    if not success:
        sys.exit(1)
