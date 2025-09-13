#!/usr/bin/env python3
"""
Script de diagnostic pour tester la connexion MySQL sur PythonAnywhere
"""
import os
import sys
import django
from pathlib import Path

# Configuration du chemin Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Configuration de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings_production')
django.setup()

from django.db import connection
from django.core.management import execute_from_command_line
import pymysql

def test_pymysql_direct():
    """Test direct de connexion PyMySQL"""
    print("🔍 Test de connexion PyMySQL directe...")
    try:
        conn = pymysql.connect(
            host='myschoolgn.mysql.pythonanywhere-services.com',
            user='myschoolgn',
            password='Faraleno1994@',
            database='myschoolgn$myschooldb',
            port=3306,
            charset='utf8mb4'
        )
        print("✅ Connexion PyMySQL directe réussie")
        
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"📊 Version MySQL: {version[0]}")
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"📋 Nombre de tables: {len(tables)}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur connexion PyMySQL: {e}")
        return False

def test_django_connection():
    """Test de connexion Django"""
    print("\n🔍 Test de connexion Django...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print("✅ Connexion Django réussie")
            return True
    except Exception as e:
        print(f"❌ Erreur connexion Django: {e}")
        return False

def test_database_operations():
    """Test des opérations de base de données"""
    print("\n🔍 Test des opérations de base de données...")
    try:
        from django.contrib.auth.models import User
        user_count = User.objects.count()
        print(f"✅ Nombre d'utilisateurs: {user_count}")
        return True
    except Exception as e:
        print(f"❌ Erreur opérations DB: {e}")
        return False

def check_database_settings():
    """Vérification des paramètres de base de données"""
    print("\n🔍 Vérification des paramètres de base de données...")
    from django.conf import settings
    
    db_config = settings.DATABASES['default']
    print(f"Engine: {db_config['ENGINE']}")
    print(f"Name: {db_config['NAME']}")
    print(f"User: {db_config['USER']}")
    print(f"Host: {db_config['HOST']}")
    print(f"Port: {db_config['PORT']}")
    print(f"Options: {db_config.get('OPTIONS', {})}")

def main():
    print("🚀 Diagnostic de connexion MySQL pour École Moderne")
    print("=" * 60)
    
    # Vérification des paramètres
    check_database_settings()
    
    # Tests de connexion
    pymysql_ok = test_pymysql_direct()
    django_ok = test_django_connection()
    
    if django_ok:
        db_ops_ok = test_database_operations()
    else:
        db_ops_ok = False
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DU DIAGNOSTIC")
    print("=" * 60)
    print(f"PyMySQL direct: {'✅ OK' if pymysql_ok else '❌ ÉCHEC'}")
    print(f"Django connection: {'✅ OK' if django_ok else '❌ ÉCHEC'}")
    print(f"Opérations DB: {'✅ OK' if db_ops_ok else '❌ ÉCHEC'}")
    
    if not pymysql_ok:
        print("\n🔧 RECOMMANDATIONS:")
        print("1. Vérifier que la base de données 'myschoolgn$myschooldb' existe")
        print("2. Vérifier les identifiants MySQL dans PythonAnywhere")
        print("3. Vérifier que l'utilisateur 'myschoolgn' a les permissions")
        print("4. Vérifier la connectivité réseau vers le serveur MySQL")
    elif not django_ok:
        print("\n🔧 RECOMMANDATIONS:")
        print("1. Vérifier la configuration Django settings_production.py")
        print("2. Vérifier que PyMySQL est installé correctement")
        print("3. Vérifier les migrations Django")
    elif not db_ops_ok:
        print("\n🔧 RECOMMANDATIONS:")
        print("1. Exécuter les migrations Django")
        print("2. Créer un superutilisateur")
        print("3. Vérifier l'intégrité des tables")

if __name__ == "__main__":
    main()
