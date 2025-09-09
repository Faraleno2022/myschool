#!/usr/bin/env python
"""
Script pour réinitialiser complètement les migrations et la base de données
"""
import os
import sys
import shutil

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

import django
django.setup()

from django.db import connection
from django.core.management import execute_from_command_line


def backup_database():
    """Sauvegarder la base de données actuelle"""
    db_file = "db.sqlite3"
    backup_file = "db_backup.sqlite3"
    
    if os.path.exists(db_file):
        shutil.copy2(db_file, backup_file)
        print(f"✅ Base de données sauvegardée: {backup_file}")
        return True
    return False


def reset_migrations():
    """Supprimer toutes les migrations problématiques"""
    print("🗑️  Suppression des migrations problématiques...")
    
    # Supprimer les fichiers de migration problématiques
    migration_files = [
        "eleves/migrations/0003_add_multi_tenant_fields.py",
        "eleves/migrations/0003_classe_code_matricule_and_more.py", 
        "eleves/migrations/0004_alter_ecole_options_ecole_couleur_principale_and_more.py"
    ]
    
    for file_path in migration_files:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"   ✅ Supprimé: {file_path}")
    
    # Nettoyer le cache Python
    pycache_dirs = [
        "eleves/migrations/__pycache__",
        "notes/migrations/__pycache__",
        "paiements/migrations/__pycache__"
    ]
    
    for cache_dir in pycache_dirs:
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            print(f"   ✅ Cache supprimé: {cache_dir}")


def create_fresh_database():
    """Créer une nouvelle base de données propre"""
    print("🆕 Création d'une nouvelle base de données...")
    
    try:
        # Supprimer l'ancienne base de données
        if os.path.exists("db.sqlite3"):
            os.remove("db.sqlite3")
            print("   ✅ Ancienne base supprimée")
        
        # Créer les nouvelles migrations
        execute_from_command_line(['manage.py', 'makemigrations'])
        print("   ✅ Nouvelles migrations créées")
        
        # Appliquer les migrations
        execute_from_command_line(['manage.py', 'migrate'])
        print("   ✅ Migrations appliquées")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def create_superuser():
    """Créer un super-utilisateur"""
    print("👤 Création du super-utilisateur...")
    
    try:
        from django.contrib.auth.models import User
        
        # Vérifier si un super-utilisateur existe déjà
        if User.objects.filter(is_superuser=True).exists():
            print("   ℹ️  Super-utilisateur existe déjà")
            return True
        
        # Créer un super-utilisateur par défaut
        User.objects.create_superuser(
            username='admin',
            email='admin@ecole-moderne.gn',
            password='admin123'
        )
        print("   ✅ Super-utilisateur créé:")
        print("      Username: admin")
        print("      Password: admin123")
        print("      ⚠️  Changez ce mot de passe en production!")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def initialize_data():
    """Initialiser les données de base"""
    print("📊 Initialisation des données de base...")
    
    try:
        execute_from_command_line(['manage.py', 'init_multi_tenant', '--create-demo-schools', '--create-templates'])
        print("   ✅ Données de base initialisées")
        return True
        
    except Exception as e:
        print(f"   ⚠️  Erreur lors de l'initialisation: {e}")
        return True  # Continue même en cas d'erreur


def main():
    """Point d'entrée principal"""
    print("🚀 Réinitialisation complète du système...\n")
    
    # 1. Sauvegarder la base actuelle
    backup_database()
    print()
    
    # 2. Nettoyer les migrations
    reset_migrations()
    print()
    
    # 3. Créer une nouvelle base de données
    if not create_fresh_database():
        print("❌ Échec de la création de la base de données")
        sys.exit(1)
    print()
    
    # 4. Créer un super-utilisateur
    create_superuser()
    print()
    
    # 5. Initialiser les données
    initialize_data()
    print()
    
    print("🎉 Réinitialisation terminée avec succès!")
    print("\n📋 Prochaines étapes:")
    print("1. Tester le système: .\\venv\\Scripts\\python.exe test_multi_tenant.py")
    print("2. Démarrer le serveur: .\\venv\\Scripts\\python.exe manage.py runserver")
    print("3. Se connecter avec admin/admin123 sur http://127.0.0.1:8000/admin/")


if __name__ == "__main__":
    main()
