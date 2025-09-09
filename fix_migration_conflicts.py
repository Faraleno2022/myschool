#!/usr/bin/env python
"""
Script pour résoudre les conflits de migration et nettoyer la base de données
"""
import os
import sys
import sqlite3

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

import django
django.setup()

from django.db import connection
from django.core.management import execute_from_command_line


def fix_slug_conflicts():
    """Résoudre les conflits de slug dans la base de données"""
    print("🔧 Résolution des conflits de slug...")
    
    try:
        with connection.cursor() as cursor:
            # 1. Vérifier si la table existe et a des données
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='eleves_ecole';")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("   ℹ️  Table eleves_ecole n'existe pas encore")
                return True
            
            # 2. Vérifier si le champ slug existe
            cursor.execute("PRAGMA table_info(eleves_ecole);")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'slug' not in columns:
                print("   ℹ️  Champ slug n'existe pas encore")
                return True
            
            # 3. Identifier les doublons de slug
            cursor.execute("""
                SELECT slug, COUNT(*) as count 
                FROM eleves_ecole 
                WHERE slug IS NOT NULL 
                GROUP BY slug 
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()
            
            if duplicates:
                print(f"   ⚠️  {len(duplicates)} slugs en doublon trouvés")
                
                # 4. Corriger les doublons
                for slug, count in duplicates:
                    cursor.execute("SELECT id, nom FROM eleves_ecole WHERE slug = ?", [slug])
                    rows = cursor.fetchall()
                    
                    # Garder le premier, modifier les autres
                    for i, (ecole_id, nom) in enumerate(rows[1:], 1):
                        import uuid
                        from django.utils.text import slugify
                        
                        base_slug = slugify(nom) if nom else "ecole"
                        new_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
                        
                        cursor.execute("UPDATE eleves_ecole SET slug = ? WHERE id = ?", [new_slug, ecole_id])
                        print(f"   ✅ Slug corrigé pour école ID {ecole_id}: {new_slug}")
            
            # 5. Corriger les slugs par défaut
            cursor.execute("SELECT id, nom FROM eleves_ecole WHERE slug = 'ecole-default'")
            default_slugs = cursor.fetchall()
            
            for ecole_id, nom in default_slugs:
                import uuid
                from django.utils.text import slugify
                
                base_slug = slugify(nom) if nom else "ecole"
                new_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
                
                cursor.execute("UPDATE eleves_ecole SET slug = ? WHERE id = ?", [new_slug, ecole_id])
                print(f"   ✅ Slug par défaut corrigé pour école ID {ecole_id}: {new_slug}")
            
            # 6. Corriger les slugs NULL
            cursor.execute("SELECT id, nom FROM eleves_ecole WHERE slug IS NULL")
            null_slugs = cursor.fetchall()
            
            for ecole_id, nom in null_slugs:
                import uuid
                from django.utils.text import slugify
                
                base_slug = slugify(nom) if nom else "ecole"
                new_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
                
                cursor.execute("UPDATE eleves_ecole SET slug = ? WHERE id = ?", [new_slug, ecole_id])
                print(f"   ✅ Slug NULL corrigé pour école ID {ecole_id}: {new_slug}")
        
        print("✅ Conflits de slug résolus!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction des slugs: {e}")
        return False


def reset_failed_migrations():
    """Réinitialiser les migrations échouées"""
    print("🔄 Réinitialisation des migrations échouées...")
    
    try:
        with connection.cursor() as cursor:
            # Supprimer les migrations échouées de la table django_migrations
            cursor.execute("""
                DELETE FROM django_migrations 
                WHERE app = 'eleves' AND name LIKE '%add_multi_tenant%'
            """)
            
            cursor.execute("""
                DELETE FROM django_migrations 
                WHERE app = 'eleves' AND name LIKE '%0003%'
            """)
            
            cursor.execute("""
                DELETE FROM django_migrations 
                WHERE app = 'eleves' AND name LIKE '%0004%'
            """)
            
        print("✅ Migrations échouées supprimées!")
        return True
        
    except Exception as e:
        print(f"⚠️  Erreur lors de la réinitialisation: {e}")
        return True  # Continue même en cas d'erreur


def apply_migrations_safely():
    """Appliquer les migrations de façon sécurisée"""
    print("📦 Application des migrations...")
    
    try:
        # Appliquer toutes les migrations en attente
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ Migrations appliquées avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors des migrations: {e}")
        return False


def main():
    """Point d'entrée principal"""
    print("🚀 Résolution des conflits de migration...\n")
    
    success = True
    
    # 1. Réinitialiser les migrations échouées
    if not reset_failed_migrations():
        success = False
    
    print()
    
    # 2. Corriger les conflits de slug
    if not fix_slug_conflicts():
        success = False
    
    print()
    
    # 3. Appliquer les migrations
    if not apply_migrations_safely():
        success = False
    
    print()
    
    if success:
        print("🎉 Tous les conflits de migration ont été résolus!")
        print("\nVous pouvez maintenant:")
        print("1. Tester le système: .\\venv\\Scripts\\python.exe test_multi_tenant.py")
        print("2. Initialiser les données: .\\venv\\Scripts\\python.exe manage.py init_multi_tenant")
        print("3. Démarrer le serveur: .\\venv\\Scripts\\python.exe manage.py runserver")
    else:
        print("❌ Certains problèmes persistent. Vérifiez les erreurs ci-dessus.")
        sys.exit(1)


if __name__ == "__main__":
    main()
