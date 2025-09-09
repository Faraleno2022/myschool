#!/usr/bin/env python
"""
Script pour réinitialiser le mot de passe PostgreSQL et résoudre les problèmes d'encodage
Usage: python reset_postgresql_password.py
"""

import os
import sys
import subprocess
import locale

def check_postgresql_service():
    """Vérifier si le service PostgreSQL est démarré"""
    print("🔧 Vérification du service PostgreSQL...")
    
    try:
        # Vérifier le statut du service PostgreSQL
        result = subprocess.run([
            'sc', 'query', 'postgresql-x64-17'
        ], capture_output=True, text=True, encoding='utf-8')
        
        if 'RUNNING' in result.stdout:
            print("✅ Service PostgreSQL est démarré")
            return True
        else:
            print("⚠️  Service PostgreSQL n'est pas démarré")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors de la vérification du service: {e}")
        return False

def start_postgresql_service():
    """Démarrer le service PostgreSQL"""
    print("🔧 Démarrage du service PostgreSQL...")
    
    try:
        result = subprocess.run([
            'net', 'start', 'postgresql-x64-17'
        ], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✅ Service PostgreSQL démarré avec succès")
            return True
        else:
            print(f"❌ Erreur lors du démarrage: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors du démarrage du service: {e}")
        return False

def reset_postgres_password():
    """Guide pour réinitialiser le mot de passe PostgreSQL"""
    print("🔧 Réinitialisation du mot de passe PostgreSQL...")
    print()
    print("ÉTAPES À SUIVRE MANUELLEMENT:")
    print("1. Ouvrez une invite de commande en tant qu'administrateur")
    print("2. Naviguez vers le dossier PostgreSQL:")
    print("   cd \"C:\\Program Files\\PostgreSQL\\17\\bin\"")
    print("3. Connectez-vous à PostgreSQL:")
    print("   psql -U postgres")
    print("4. Si demandé, utilisez le mot de passe que vous avez défini lors de l'installation")
    print("5. Une fois connecté, changez le mot de passe:")
    print("   ALTER USER postgres PASSWORD 'nouveaumotdepasse';")
    print("6. Quittez PostgreSQL:")
    print("   \\q")
    print()
    print("ALTERNATIVE - Réinitialisation complète:")
    print("1. Arrêtez le service PostgreSQL:")
    print("   net stop postgresql-x64-17")
    print("2. Modifiez le fichier pg_hba.conf pour permettre l'accès sans mot de passe")
    print("3. Redémarrez le service et changez le mot de passe")
    print()

def create_simple_env():
    """Créer un fichier .env avec une configuration simple"""
    print("🔧 Création d'un fichier .env simplifié...")
    
    env_content = """# Configuration de base pour École Moderne
DEBUG=True
SECRET_KEY=votre-cle-secrete-django

# Base de données - SQLite par défaut (sans problème d'encodage)
DATABASE_ENGINE=sqlite3

# Configuration PostgreSQL (à activer quand le mot de passe est configuré)
# DATABASE_ENGINE=postgresql
# DATABASE_NAME=ecole_moderne
# DATABASE_USER=postgres
# DATABASE_PASSWORD=motdepassesimple
# DATABASE_HOST=localhost
# DATABASE_PORT=5432

# Autres paramètres
ALLOWED_HOSTS=localhost,127.0.0.1
MEDIA_ROOT=media/
STATIC_ROOT=static/
"""
    
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("✅ Fichier .env créé avec configuration SQLite par défaut")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création du .env: {e}")
        return False

def test_sqlite_fallback():
    """Tester que Django fonctionne avec SQLite"""
    print("🔧 Test de Django avec SQLite...")
    
    try:
        # Forcer l'encodage UTF-8
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['DATABASE_ENGINE'] = 'sqlite3'
        
        # Configuration Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
        
        import django
        django.setup()
        
        from django.db import connection
        
        # Test de connexion
        with connection.cursor() as cursor:
            cursor.execute('SELECT sqlite_version();')
            version = cursor.fetchone()[0]
            
        print(f"✅ Django fonctionne avec SQLite version {version}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur avec SQLite: {e}")
        return False

def main():
    print("🚀 Résolution des problèmes PostgreSQL - École Moderne")
    print("=" * 60)
    
    # Afficher les informations système
    print(f"Encodage système: {locale.getpreferredencoding()}")
    print(f"Python version: {sys.version}")
    print()
    
    # Étape 1: Vérifier le service PostgreSQL
    service_running = check_postgresql_service()
    
    if not service_running:
        print("Tentative de démarrage du service...")
        service_running = start_postgresql_service()
    
    # Étape 2: Créer un .env simplifié
    create_simple_env()
    
    # Étape 3: Tester SQLite comme solution de secours
    if test_sqlite_fallback():
        print("\n🎉 SOLUTION TEMPORAIRE FONCTIONNELLE:")
        print("   Votre projet fonctionne maintenant avec SQLite")
        print("   Vous pouvez exécuter: python manage.py runserver")
        print()
    
    # Étape 4: Instructions pour PostgreSQL
    print("📋 POUR CONFIGURER POSTGRESQL PLUS TARD:")
    reset_postgres_password()
    
    print("\n" + "=" * 60)
    print("✅ Configuration terminée!")
    print("\nPROCHAINES ÉTAPES:")
    print("1. Testez votre application avec: python manage.py runserver")
    print("2. Si vous voulez PostgreSQL, suivez les instructions ci-dessus")
    print("3. Une fois PostgreSQL configuré, modifiez DATABASE_ENGINE dans .env")

if __name__ == '__main__':
    main()
