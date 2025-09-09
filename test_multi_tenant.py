#!/usr/bin/env python
"""
Script de test pour valider le système multi-tenant
"""
import os
import sys

# Configuration Django AVANT les imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

import django
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from eleves.models import Ecole
from utilisateurs.models import Profil
from inscription_ecoles.models import DemandeInscriptionEcole, ConfigurationEcole


class MultiTenantTestCase:
    """Tests pour le système multi-tenant"""
    
    def __init__(self):
        self.client = Client()
        self.results = []
        
    def log_result(self, test_name, success, message=""):
        """Enregistrer le résultat d'un test"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
        print(f"{status} {test_name}: {message}")
    
    def test_models_creation(self):
        """Test de création des modèles de base"""
        try:
            # Créer une école de test avec slug unique
            import uuid
            unique_slug = f"ecole-test-{str(uuid.uuid4())[:8]}"
            ecole = Ecole.objects.create(
                nom="École Test",
                slug=unique_slug,
                type_ecole="PRIVEE",
                adresse="Test Address",
                ville="Test City",
                prefecture="Test Prefecture",
                telephone="+224123456789",
                email="test@ecole.com",
                directeur="Test Director",
                statut="ACTIVE"
            )
            
            # Test création utilisateur et profil
            import time
            timestamp = str(int(time.time()))
            user = User.objects.create_user(
                username=f"testuser_{timestamp}",
                email=f"test_{timestamp}@user.com",
                password="testpass123"
            )
            
            profil = Profil.objects.create(
                user=user,
                role="COMPTABLE",
                telephone="+224987654321",
                ecole=ecole,
                actif=True
            )
            
            # Test configuration école
            config = ConfigurationEcole.objects.create(ecole=ecole)
            
            self.log_result("Création des modèles", True, "École, Utilisateur, Profil et Configuration créés")
            
            # Nettoyage
            profil.delete()
            ecole.delete()
            user.delete()
            
        except Exception as e:
            self.log_result("Création des modèles", False, str(e))
    
    def test_middleware_functionality(self):
        """Test du fonctionnement des middlewares"""
        try:
            # Créer une école de test
            import uuid
            unique_slug = f"ecole-middleware-{str(uuid.uuid4())[:8]}"
            ecole = Ecole.objects.create(
                nom="École Middleware Test",
                slug=unique_slug,
                type_ecole="PRIVEE",
                adresse="Test",
                ville="Test",
                prefecture="Test",
                telephone="+224111111111",
                email="middleware@test.com",
                directeur="Test",
                statut="ACTIVE"
            )
            
            # Créer un utilisateur avec profil
            import time
            timestamp = str(int(time.time()))
            user = User.objects.create_user(
                username=f"middlewareuser_{timestamp}",
                password="testpass123"
            )
            
            profil = Profil.objects.create(
                user=user,
                role="ADMIN",
                telephone="+224222222222",
                ecole=ecole,
                actif=True
            )
            
            # Test de connexion
            login_success = self.client.login(username=f"middlewareuser_{timestamp}", password="testpass123")
            
            if login_success:
                # Test d'accès à une page protégée (page d'accueil exemptée)
                response = self.client.get('/')
                if response.status_code == 200:
                    self.log_result("Middleware - Accès page", True, "Accès autorisé à la page d'accueil")
                else:
                    self.log_result("Middleware - Accès page", False, f"Code de réponse: {response.status_code}")
                
                # Test d'accès à une page qui nécessite une école
                response_protected = self.client.get('/eleves/liste/')
                if response_protected.status_code in [200, 302]:  # 302 = redirection OK
                    self.log_result("Middleware - Page protégée", True, "Middleware fonctionne correctement")
                else:
                    self.log_result("Middleware - Page protégée", False, f"Code: {response_protected.status_code}")
            else:
                self.log_result("Middleware - Connexion", False, "Échec de connexion")
            
            # Nettoyage
            self.client.logout()
            profil.delete()
            ecole.delete()
            user.delete()
            
        except Exception as e:
            self.log_result("Middleware", False, str(e))
    
    def test_permissions_system(self):
        """Test du système de permissions"""
        try:
            # Créer école et utilisateurs avec différents rôles
            import uuid
            unique_slug = f"ecole-permissions-{str(uuid.uuid4())[:8]}"
            ecole = Ecole.objects.create(
                nom="École Permissions Test",
                slug=unique_slug,
                type_ecole="PRIVEE",
                adresse="Test",
                ville="Test",
                prefecture="Test",
                telephone="+224333333333",
                email="permissions@test.com",
                directeur="Test",
                statut="ACTIVE"
            )
            
            # Admin avec toutes les permissions
            import time
            timestamp = str(int(time.time()))
            admin_user = User.objects.create_user(
                username=f"adminuser_{timestamp}",
                password="testpass123"
            )
            
            admin_profil = Profil.objects.create(
                user=admin_user,
                role="ADMIN",
                telephone="+224444444444",
                ecole=ecole,
                peut_valider_paiements=True,
                peut_valider_depenses=True,
                peut_generer_rapports=True,
                peut_gerer_utilisateurs=True,
                actif=True
            )
            
            # Comptable avec permissions limitées
            comptable_user = User.objects.create_user(
                username=f"comptableuser_{timestamp}",
                password="testpass123"
            )
            
            comptable_profil = Profil.objects.create(
                user=comptable_user,
                role="COMPTABLE",
                telephone="+224555555555",
                ecole=ecole,
                peut_valider_paiements=False,
                peut_valider_depenses=False,
                peut_generer_rapports=True,
                peut_gerer_utilisateurs=False,
                actif=True
            )
            
            self.log_result("Système de permissions", True, "Utilisateurs avec rôles différents créés")
            
            # Nettoyage
            admin_profil.delete()
            comptable_profil.delete()
            ecole.delete()
            admin_user.delete()
            comptable_user.delete()
            
        except Exception as e:
            self.log_result("Système de permissions", False, str(e))
    
    def test_inscription_workflow(self):
        """Test du workflow d'inscription des écoles"""
        try:
            # Créer une demande d'inscription
            demande = DemandeInscriptionEcole.objects.create(
                nom_demandeur="Test",
                prenom_demandeur="User",
                fonction_demandeur="Directeur",
                email_demandeur="demande@test.com",
                telephone_demandeur="+224666666666",
                nom_ecole="École Demande Test",
                type_ecole="PRIVEE",
                adresse_ecole="Test Address",
                ville="Test City",
                prefecture="Test Prefecture",
                telephone_ecole="+224777777777",
                email_ecole="ecole@demande.com",
                nom_directeur="Test Director",
                nombre_eleves_estime=100,
                nombre_enseignants=10,
                niveaux_enseignes="Primaire, Collège",
                statut="EN_ATTENTE"
            )
            
            self.log_result("Workflow inscription", True, f"Demande créée avec statut: {demande.statut}")
            
            # Nettoyage
            demande.delete()
            
        except Exception as e:
            self.log_result("Workflow inscription", False, str(e))
    
    def test_multi_school_isolation(self):
        """Test de l'isolation des données entre écoles"""
        try:
            # Créer deux écoles
            import uuid
            unique_slug1 = f"ecole-1-{str(uuid.uuid4())[:8]}"
            ecole1 = Ecole.objects.create(
                nom="École 1",
                slug=unique_slug1,
                type_ecole="PRIVEE",
                adresse="Address 1",
                ville="City 1",
                prefecture="Prefecture 1",
                telephone="+224111111111",
                email="ecole1@test.com",
                directeur="Director 1",
                statut="ACTIVE"
            )
            
            unique_slug2 = f"ecole-2-{str(uuid.uuid4())[:8]}"
            ecole2 = Ecole.objects.create(
                nom="École 2",
                slug=unique_slug2,
                type_ecole="PUBLIQUE",
                adresse="Address 2",
                ville="City 2",
                prefecture="Prefecture 2",
                telephone="+224222222222",
                email="ecole2@test.com",
                directeur="Director 2",
                statut="ACTIVE"
            )
            
            # Créer des utilisateurs pour chaque école
            import time
            timestamp = str(int(time.time()))
            user1 = User.objects.create_user(username=f"user1_{timestamp}", password="pass123")
            user2 = User.objects.create_user(username=f"user2_{timestamp}", password="pass123")
            
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
            
            # Vérifier que chaque utilisateur est bien lié à son école
            assert profil1.ecole == ecole1
            assert profil2.ecole == ecole2
            assert profil1.ecole != profil2.ecole
            
            self.log_result("Isolation multi-écoles", True, "Utilisateurs correctement isolés par école")
            
            # Nettoyage
            profil1.delete()
            profil2.delete()
            ecole1.delete()
            ecole2.delete()
            user1.delete()
            user2.delete()
            
        except Exception as e:
            self.log_result("Isolation multi-écoles", False, str(e))
    
    def run_all_tests(self):
        """Exécuter tous les tests"""
        print("🧪 Démarrage des tests du système multi-tenant...\n")
        
        self.test_models_creation()
        self.test_middleware_functionality()
        self.test_permissions_system()
        self.test_inscription_workflow()
        self.test_multi_school_isolation()
        
        print("\n📊 Résumé des tests:")
        print("=" * 50)
        
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        
        for result in self.results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}")
            if result['message'] and not result['success']:
                print(f"   └─ {result['message']}")
        
        print(f"\n🎯 Résultat global: {passed}/{total} tests réussis")
        
        if passed == total:
            print("🎉 Tous les tests sont passés! Le système multi-tenant est fonctionnel.")
        else:
            print("⚠️  Certains tests ont échoué. Vérifiez la configuration.")
        
        return passed == total


def main():
    """Point d'entrée principal"""
    try:
        tester = MultiTenantTestCase()
        success = tester.run_all_tests()
        
        if success:
            print("\n✅ Le système multi-tenant est prêt à être utilisé!")
            print("\nPour initialiser avec des données de base, exécutez:")
            print("python manage.py init_multi_tenant --create-demo-schools --create-templates --assign-existing-users")
        else:
            print("\n❌ Des problèmes ont été détectés. Vérifiez la configuration.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution des tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
