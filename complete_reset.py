#!/usr/bin/env python
"""
Script pour réinitialisation complète - supprime tout et recrée proprement
"""
import os
import sys
import shutil
import glob

def clean_migrations():
    """Supprimer toutes les migrations sauf __init__.py"""
    print("🧹 Nettoyage complet des migrations...")
    
    apps = ['eleves', 'utilisateurs', 'paiements', 'notes', 'rapports', 'depenses', 'salaires', 'bus', 'inscription_ecoles', 'administration']
    
    for app in apps:
        migration_dir = f"{app}/migrations"
        if os.path.exists(migration_dir):
            # Supprimer tous les fichiers sauf __init__.py
            for file in glob.glob(f"{migration_dir}/*.py"):
                if not file.endswith("__init__.py"):
                    os.remove(file)
                    print(f"   ✅ Supprimé: {file}")
            
            # Supprimer le cache
            pycache = f"{migration_dir}/__pycache__"
            if os.path.exists(pycache):
                shutil.rmtree(pycache)
                print(f"   ✅ Cache supprimé: {pycache}")


def clean_database():
    """Supprimer la base de données"""
    print("🗑️  Suppression de la base de données...")
    
    if os.path.exists("db.sqlite3"):
        # Sauvegarder d'abord
        if os.path.exists("db_backup.sqlite3"):
            os.remove("db_backup.sqlite3")
        shutil.copy2("db.sqlite3", "db_backup.sqlite3")
        print("   ✅ Sauvegarde créée: db_backup.sqlite3")
        
        os.remove("db.sqlite3")
        print("   ✅ Base de données supprimée")


def recreate_system():
    """Recréer le système complet"""
    print("🔄 Recréation du système...")
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
    
    import django
    django.setup()
    
    from django.core.management import execute_from_command_line
    
    try:
        # 1. Créer les migrations
        print("   📝 Création des migrations...")
        execute_from_command_line(['manage.py', 'makemigrations'])
        
        # 2. Appliquer les migrations
        print("   📦 Application des migrations...")
        execute_from_command_line(['manage.py', 'migrate'])
        
        # 3. Créer un super-utilisateur
        print("   👤 Création du super-utilisateur...")
        from django.contrib.auth.models import User
        
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@ecole-moderne.gn',
                password='admin123'
            )
            print("      ✅ Super-utilisateur créé (admin/admin123)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def main():
    """Point d'entrée principal"""
    print("🚀 RÉINITIALISATION COMPLÈTE DU SYSTÈME\n")
    print("⚠️  Cette opération va supprimer toutes les données existantes!")
    
    # 1. Nettoyer les migrations
    clean_migrations()
    print()
    
    # 2. Supprimer la base de données
    clean_database()
    print()
    
    # 3. Recréer le système
    if recreate_system():
        print("\n🎉 Système réinitialisé avec succès!")
        print("\n📋 Prochaines étapes:")
        print("1. Tester: .\\venv\\Scripts\\python.exe test_multi_tenant.py")
        print("2. Initialiser: .\\venv\\Scripts\\python.exe manage.py init_multi_tenant --create-demo-schools --create-templates")
        print("3. Serveur: .\\venv\\Scripts\\python.exe manage.py runserver")
        print("4. Admin: http://127.0.0.1:8000/admin/ (admin/admin123)")
    else:
        print("\n❌ Échec de la réinitialisation")
        sys.exit(1)


if __name__ == "__main__":
    main()
