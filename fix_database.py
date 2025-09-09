#!/usr/bin/env python
"""
Script pour résoudre les problèmes de base de données et migrations
"""
import os
import sys
import sqlite3

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

import django
django.setup()

from django.core.management import execute_from_command_line
from django.db import connection
from eleves.models import Ecole
from utilisateurs.models import Profil


def fix_database_constraints():
    """Résoudre les problèmes de contraintes de base de données"""
    print("🔧 Résolution des problèmes de base de données...")
    
    try:
        # 1. Vérifier et corriger les écoles avec des slugs en conflit
        print("📝 Vérification des slugs d'écoles...")
        
        ecoles_sans_slug = Ecole.objects.filter(slug__isnull=True)
        ecoles_slug_default = Ecole.objects.filter(slug="ecole-default")
        
        print(f"   - Écoles sans slug: {ecoles_sans_slug.count()}")
        print(f"   - Écoles avec slug par défaut: {ecoles_slug_default.count()}")
        
        # Corriger les slugs
        for i, ecole in enumerate(ecoles_sans_slug):
            from django.utils.text import slugify
            import uuid
            base_slug = slugify(ecole.nom) or "ecole"
            unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
            ecole.slug = unique_slug
            ecole.save()
            print(f"   ✅ Slug généré pour {ecole.nom}: {unique_slug}")
        
        for i, ecole in enumerate(ecoles_slug_default):
            from django.utils.text import slugify
            import uuid
            base_slug = slugify(ecole.nom) or "ecole"
            unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
            ecole.slug = unique_slug
            ecole.save()
            print(f"   ✅ Slug corrigé pour {ecole.nom}: {unique_slug}")
        
        # 2. Vérifier les profils utilisateurs
        print("👥 Vérification des profils utilisateurs...")
        
        from django.contrib.auth.models import User
        users_sans_profil = User.objects.filter(profil__isnull=True)
        profils_sans_ecole = Profil.objects.filter(ecole__isnull=True)
        
        print(f"   - Utilisateurs sans profil: {users_sans_profil.count()}")
        print(f"   - Profils sans école: {profils_sans_ecole.count()}")
        
        # Créer une école par défaut si nécessaire
        ecole_defaut = Ecole.objects.first()
        if not ecole_defaut:
            ecole_defaut = Ecole.objects.create(
                nom="École Moderne",
                slug="ecole-moderne-default",
                type_ecole="PRIVEE",
                adresse="Conakry, Guinée",
                ville="Conakry",
                prefecture="Conakry",
                telephone="+224622613559",
                email="contact@ecole-moderne.gn",
                directeur="Direction Générale",
                statut="ACTIVE"
            )
            print(f"   ✅ École par défaut créée: {ecole_defaut.nom}")
        
        # Assigner les profils sans école
        for profil in profils_sans_ecole:
            profil.ecole = ecole_defaut
            profil.save()
            print(f"   ✅ École assignée au profil: {profil.user.username}")
        
        print("✅ Problèmes de base de données résolus!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        return False


def reset_migrations():
    """Réinitialiser les migrations si nécessaire"""
    print("🔄 Vérification des migrations...")
    
    try:
        # Appliquer les migrations en attente
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ Migrations appliquées avec succès!")
        return True
    except Exception as e:
        print(f"⚠️  Problème avec les migrations: {e}")
        return False


def main():
    """Point d'entrée principal"""
    print("🚀 Démarrage de la correction de la base de données...\n")
    
    success = True
    
    # 1. Corriger les contraintes
    if not fix_database_constraints():
        success = False
    
    print()
    
    # 2. Appliquer les migrations
    if not reset_migrations():
        success = False
    
    print()
    
    if success:
        print("🎉 Toutes les corrections ont été appliquées avec succès!")
        print("\nVous pouvez maintenant:")
        print("1. Exécuter: python test_multi_tenant.py")
        print("2. Démarrer le serveur: python manage.py runserver")
        print("3. Initialiser les données: python manage.py init_multi_tenant")
    else:
        print("❌ Certaines corrections ont échoué. Vérifiez les erreurs ci-dessus.")
        sys.exit(1)


if __name__ == "__main__":
    main()
