#!/usr/bin/env python
"""
Script de test pour vérifier les corrections urgentes
- Vérification des URLs
- Test de connexion
- Validation du système multi-tenant
"""

import os
import sys
import django
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

User = get_user_model()

def test_urls_resolution():
    """Test de résolution des URLs problématiques"""
    print("🔍 Test de résolution des URLs...")
    
    try:
        # Test URL admin_demandes_inscription
        url = reverse('inscription_ecoles:admin_demandes_inscription')
        print(f"✅ URL admin_demandes_inscription: {url}")
        
        # Test autres URLs critiques
        urls_to_test = [
            'eleves:liste_eleves',
            'utilisateurs:login',
            'inscription_ecoles:inscription_ecole',
        ]
        
        for url_name in urls_to_test:
            try:
                url = reverse(url_name)
                print(f"✅ URL {url_name}: {url}")
            except Exception as e:
                print(f"❌ Erreur URL {url_name}: {e}")
                
    except Exception as e:
        print(f"❌ Erreur générale URLs: {e}")

def test_user_login():
    """Test de connexion utilisateur"""
    print("\n🔐 Test de connexion utilisateur...")
    
    try:
        # Vérifier si le superuser LENO existe
        user = User.objects.filter(username='LENO').first()
        if user:
            print(f"✅ Utilisateur LENO trouvé: {user.username}")
            print(f"   - Superuser: {user.is_superuser}")
            print(f"   - Staff: {user.is_staff}")
            print(f"   - Actif: {user.is_active}")
        else:
            print("❌ Utilisateur LENO non trouvé")
            
    except Exception as e:
        print(f"❌ Erreur test utilisateur: {e}")

def test_client_requests():
    """Test des requêtes client"""
    print("\n🌐 Test des requêtes client...")
    
    client = Client()
    
    try:
        # Test page d'accueil
        response = client.get('/')
        print(f"✅ Page d'accueil: Status {response.status_code}")
        
        # Test page de login
        response = client.get('/utilisateurs/login/')
        print(f"✅ Page login: Status {response.status_code}")
        
        # Test avec utilisateur connecté
        user = User.objects.filter(username='LENO').first()
        if user:
            client.force_login(user)
            response = client.get('/eleves/liste/')
            print(f"✅ Liste élèves (connecté): Status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erreur requêtes client: {e}")

def main():
    """Fonction principale"""
    print("🚀 TESTS DE CORRECTIONS URGENTES")
    print("=" * 50)
    
    test_urls_resolution()
    test_user_login()
    test_client_requests()
    
    print("\n" + "=" * 50)
    print("✅ Tests terminés!")
    print("\n💡 Prochaines étapes:")
    print("   1. Redémarrer le serveur Django")
    print("   2. Tester la connexion avec LENO")
    print("   3. Naviguer vers /eleves/liste/")

if __name__ == '__main__':
    main()
