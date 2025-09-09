#!/usr/bin/env python
"""
Script pour résoudre les problèmes d'encodage PostgreSQL
Usage: python fix_postgresql.py
"""

import os
import sys
import locale

# Forcer l'encodage UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LANG'] = 'en_US.UTF-8'

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

try:
    import django
    django.setup()
except Exception as e:
    print(f"❌ Erreur lors de l'initialisation Django: {e}")
    sys.exit(1)

def test_postgresql_connection():
    """Tester la connexion PostgreSQL avec gestion d'encodage"""
    print("🔧 Test de connexion PostgreSQL avec encodage UTF-8...")
    
    try:
        import psycopg2
        
        # Paramètres de connexion avec encodage explicite
        conn_params = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': 'postgres',
            'dbname': 'postgres',
            'client_encoding': 'UTF8'
        }
        
        # Test de connexion
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Test simple
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        
        print(f"✅ Connexion PostgreSQL réussie!")
        print(f"   Version: {version[:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur de connexion PostgreSQL: {e}")
        return False

def create_database():
    """Créer la base de données ecole_moderne"""
    print("🔧 Création de la base de données ecole_moderne...")
    
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        # Connexion à la base postgres par défaut
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password='postgres',
            dbname='postgres',
            client_encoding='UTF8'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        cursor = conn.cursor()
        
        # Vérifier si la base existe
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'ecole_moderne'"
        )
        
        if cursor.fetchone():
            print("✅ Base de données 'ecole_moderne' existe déjà")
        else:
            # Créer la base de données
            cursor.execute('CREATE DATABASE ecole_moderne WITH ENCODING UTF8')
            print("✅ Base de données 'ecole_moderne' créée avec succès")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de la base: {e}")
        return False

def test_django_connection():
    """Tester la connexion Django avec PostgreSQL"""
    print("🔧 Test de connexion Django avec PostgreSQL...")
    
    try:
        from django.db import connection
        
        # Forcer la connexion
        with connection.cursor() as cursor:
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]
            
        print(f"✅ Connexion Django-PostgreSQL réussie!")
        print(f"   Version: {version[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Erreur de connexion Django: {e}")
        return False

def run_migrations():
    """Effectuer les migrations Django"""
    print("🔧 Exécution des migrations Django...")
    
    try:
        from django.core.management import call_command
        
        # Créer les migrations
        call_command('makemigrations', verbosity=1)
        
        # Appliquer les migrations
        call_command('migrate', verbosity=1)
        
        print("✅ Migrations terminées avec succès")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors des migrations: {e}")
        return False

def main():
    print("🚀 Résolution des problèmes PostgreSQL pour École Moderne")
    print("=" * 60)
    
    # Afficher les informations d'encodage
    print(f"Encodage système: {locale.getpreferredencoding()}")
    print(f"PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'Non défini')}")
    print()
    
    success = True
    
    # Test 1: Connexion PostgreSQL directe
    if not test_postgresql_connection():
        success = False
        print("\n⚠️  Vérifiez que PostgreSQL est installé et démarré")
        print("   Mot de passe par défaut utilisé: 'postgres'")
        return False
    
    # Test 2: Création de la base de données
    if not create_database():
        success = False
    
    # Test 3: Connexion Django
    if not test_django_connection():
        success = False
    
    # Test 4: Migrations
    if success and not run_migrations():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Configuration PostgreSQL terminée avec succès!")
        print("\nVotre projet École Moderne est maintenant configuré avec PostgreSQL")
        print("Vous pouvez maintenant exécuter: python manage.py runserver")
    else:
        print("⚠️  Configuration terminée avec des erreurs")
        print("Vérifiez les messages d'erreur ci-dessus")
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
