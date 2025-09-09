#!/usr/bin/env python
"""
Script simple pour configurer PostgreSQL avec Django
Usage: python setup_postgresql.py [options]
"""

import os
import sys
import django
from pathlib import Path

# Configuration Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

try:
    django.setup()
except Exception as e:
    print(f"❌ Erreur lors de l'initialisation Django: {e}")
    sys.exit(1)

from django.core.management import call_command
from django.db import connection
from django.conf import settings
import argparse


def check_postgresql_config():
    """Vérifier que PostgreSQL est configuré"""
    db_engine = os.environ.get('DATABASE_ENGINE', 'sqlite3')
    
    if db_engine != 'postgresql':
        print("❌ PostgreSQL n'est pas configuré.")
        print("   Modifiez votre fichier .env et définissez DATABASE_ENGINE=postgresql")
        print("   Puis configurez les variables DATABASE_NAME, DATABASE_USER, etc.")
        return False

    db_config = settings.DATABASES['default']
    required_fields = ['NAME', 'USER', 'HOST', 'PORT']
    
    missing_fields = []
    for field in required_fields:
        if not db_config.get(field):
            missing_fields.append(f'DATABASE_{field}')
    
    if missing_fields:
        print("❌ Configuration PostgreSQL incomplète:")
        for field in missing_fields:
            print(f"   - {field} manquant dans le fichier .env")
        return False

    print("✅ Configuration PostgreSQL détectée")
    return True


def create_database():
    """Créer la base de données PostgreSQL"""
    print("🔄 Tentative de création de la base de données...")
    
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        db_config = settings.DATABASES['default']
        
        # Connexion au serveur PostgreSQL
        conn = psycopg2.connect(
            host=db_config['HOST'],
            port=db_config['PORT'],
            user=db_config['USER'],
            password=db_config['PASSWORD'],
            database='postgres'  # Base par défaut
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        cursor = conn.cursor()
        
        # Vérifier si la base existe
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            [db_config['NAME']]
        )
        
        if cursor.fetchone():
            print(f"⚠️  Base de données '{db_config['NAME']}' existe déjà")
        else:
            cursor.execute(f'CREATE DATABASE "{db_config["NAME"]}"')
            print(f"✅ Base de données '{db_config['NAME']}' créée")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de la base: {e}")
        print("   Vérifiez que PostgreSQL est installé et démarré")
        print("   Vérifiez les paramètres de connexion dans .env")
        return False


def test_connection():
    """Tester la connexion à PostgreSQL"""
    print("🔄 Test de connexion à PostgreSQL...")
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version()')
            version = cursor.fetchone()[0]
            print(f"✅ Connexion réussie: {version}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False


def run_migrations():
    """Effectuer les migrations Django"""
    print("🔄 Exécution des migrations...")
    
    try:
        print("   - Création des migrations...")
        call_command('makemigrations', verbosity=1)
        
        print("   - Application des migrations...")
        call_command('migrate', verbosity=1)
        
        print("✅ Migrations terminées")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors des migrations: {e}")
        return False


def create_superuser():
    """Créer un superutilisateur si nécessaire"""
    print("🔄 Vérification des superutilisateurs...")
    
    try:
        from django.contrib.auth.models import User
        
        if User.objects.filter(is_superuser=True).exists():
            print("✅ Un superutilisateur existe déjà")
            return True
        
        print("   Aucun superutilisateur trouvé. Création...")
        call_command('createsuperuser', interactive=True)
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création du superutilisateur: {e}")
        return False


def show_status():
    """Afficher le statut de la configuration"""
    print("\n" + "="*50)
    print("📊 STATUT DE LA CONFIGURATION")
    print("="*50)
    
    try:
        from django.contrib.auth.models import User
        from eleves.models import Eleve
        from paiements.models import Paiement
        
        user_count = User.objects.count()
        eleve_count = Eleve.objects.count()
        paiement_count = Paiement.objects.count()
        
        print(f"👥 Utilisateurs: {user_count}")
        print(f"🎓 Élèves: {eleve_count}")
        print(f"💰 Paiements: {paiement_count}")
        
        # Informations sur la base
        db_config = settings.DATABASES['default']
        print(f"🗄️  Base: {db_config['NAME']} sur {db_config['HOST']}:{db_config['PORT']}")
        
    except Exception as e:
        print(f"⚠️  Impossible d'afficher les statistiques: {e}")


def main():
    parser = argparse.ArgumentParser(description='Configuration PostgreSQL pour École Moderne')
    parser.add_argument('--create-db', action='store_true', help='Créer la base de données')
    parser.add_argument('--migrate', action='store_true', help='Effectuer les migrations')
    parser.add_argument('--superuser', action='store_true', help='Créer un superutilisateur')
    parser.add_argument('--all', action='store_true', help='Effectuer toutes les opérations')
    
    args = parser.parse_args()
    
    print("🚀 Configuration PostgreSQL pour École Moderne")
    print("="*50)
    
    # Vérifier la configuration
    if not check_postgresql_config():
        print("\n📝 Pour configurer PostgreSQL:")
        print("1. Modifiez votre fichier .env")
        print("2. Définissez DATABASE_ENGINE=postgresql")
        print("3. Configurez DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, etc.")
        return False
    
    success = True
    
    # Créer la base si demandé
    if args.create_db or args.all:
        if not create_database():
            success = False
    
    # Tester la connexion
    if not test_connection():
        return False
    
    # Migrations
    if args.migrate or args.all:
        if not run_migrations():
            success = False
    
    # Superutilisateur
    if args.superuser or args.all:
        if not create_superuser():
            success = False
    
    # Afficher le statut
    show_status()
    
    if success:
        print("\n🎉 Configuration terminée avec succès!")
        print("\n📝 Prochaines étapes:")
        print("1. Testez votre application: python manage.py runserver")
        print("2. Connectez-vous à l'admin Django")
        print("3. Configurez les sauvegardes régulières")
    else:
        print("\n⚠️  Configuration terminée avec des erreurs")
    
    return success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
