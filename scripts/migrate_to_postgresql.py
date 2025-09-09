#!/usr/bin/env python
"""
Script pour migrer les données de SQLite vers PostgreSQL
Usage: python scripts/migrate_to_postgresql.py
"""

import os
import sys
import django
from pathlib import Path

# Ajouter le répertoire du projet au path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.core.management import call_command
from django.db import connections
from django.conf import settings
import json
import tempfile


def backup_sqlite_data():
    """Sauvegarder les données SQLite en JSON"""
    print("🔄 Sauvegarde des données SQLite...")
    
    # Forcer l'utilisation de SQLite temporairement
    original_engine = os.environ.get('DATABASE_ENGINE', 'sqlite3')
    os.environ['DATABASE_ENGINE'] = 'sqlite3'
    
    # Recharger les settings
    from importlib import reload
    from django.conf import settings
    reload(settings)
    
    try:
        # Créer un fichier de sauvegarde temporaire
        backup_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        
        # Exporter toutes les données
        call_command('dumpdata', 
                    '--natural-foreign', 
                    '--natural-primary',
                    '--exclude=contenttypes',
                    '--exclude=auth.permission',
                    '--exclude=sessions',
                    '--output=' + backup_file.name)
        
        print(f"✅ Données sauvegardées dans: {backup_file.name}")
        return backup_file.name
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return None
    finally:
        # Restaurer la configuration originale
        os.environ['DATABASE_ENGINE'] = original_engine


def setup_postgresql():
    """Configurer PostgreSQL et effectuer les migrations"""
    print("🔄 Configuration de PostgreSQL...")
    
    # S'assurer que PostgreSQL est configuré
    os.environ['DATABASE_ENGINE'] = 'postgresql'
    
    try:
        # Exécuter la commande de setup PostgreSQL
        call_command('setup_postgresql', '--create-db', '--migrate')
        print("✅ PostgreSQL configuré avec succès")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la configuration PostgreSQL: {e}")
        return False


def restore_data(backup_file):
    """Restaurer les données dans PostgreSQL"""
    print("🔄 Restauration des données dans PostgreSQL...")
    
    try:
        # Charger les données
        call_command('loaddata', backup_file)
        print("✅ Données restaurées avec succès")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la restauration: {e}")
        return False


def verify_migration():
    """Vérifier que la migration s'est bien passée"""
    print("🔄 Vérification de la migration...")
    
    try:
        from django.contrib.auth.models import User
        from eleves.models import Eleve
        from paiements.models import Paiement
        
        user_count = User.objects.count()
        eleve_count = Eleve.objects.count()
        paiement_count = Paiement.objects.count()
        
        print(f"📊 Statistiques après migration:")
        print(f"   - Utilisateurs: {user_count}")
        print(f"   - Élèves: {eleve_count}")
        print(f"   - Paiements: {paiement_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False


def main():
    """Fonction principale de migration"""
    print("🚀 Début de la migration SQLite → PostgreSQL")
    print("=" * 50)
    
    # Vérifier que les variables d'environnement PostgreSQL sont définies
    required_vars = ['DATABASE_NAME', 'DATABASE_USER', 'DATABASE_PASSWORD', 'DATABASE_HOST']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print("❌ Variables d'environnement manquantes:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nVeuillez configurer votre fichier .env avec les paramètres PostgreSQL")
        return False
    
    # Étape 1: Sauvegarder les données SQLite
    backup_file = backup_sqlite_data()
    if not backup_file:
        return False
    
    # Étape 2: Configurer PostgreSQL
    if not setup_postgresql():
        return False
    
    # Étape 3: Restaurer les données
    if not restore_data(backup_file):
        return False
    
    # Étape 4: Vérifier la migration
    if not verify_migration():
        return False
    
    # Nettoyer le fichier de sauvegarde
    try:
        os.unlink(backup_file)
        print(f"🧹 Fichier de sauvegarde supprimé: {backup_file}")
    except:
        pass
    
    print("=" * 50)
    print("🎉 Migration terminée avec succès!")
    print("\n📝 Prochaines étapes:")
    print("1. Testez votre application avec PostgreSQL")
    print("2. Sauvegardez votre ancienne base SQLite si nécessaire")
    print("3. Configurez les sauvegardes régulières PostgreSQL")
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
