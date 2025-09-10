#!/usr/bin/env python3
"""
Script de déploiement automatisé pour www.myschoolgn.space
École Moderne - Système Multi-Tenant
"""

import os
import sys
import subprocess
import django
from pathlib import Path

def run_command(command, description):
    """Exécute une commande et affiche le résultat"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - Succès")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"❌ {description} - Erreur")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution: {e}")
        return False
    return True

def main():
    print("🚀 Déploiement École Moderne sur www.myschoolgn.space")
    print("=" * 60)
    
    # Vérifier que nous sommes dans le bon répertoire
    if not os.path.exists('manage.py'):
        print("❌ Erreur: manage.py non trouvé. Exécutez ce script depuis le répertoire du projet.")
        sys.exit(1)
    
    # 1. Créer les répertoires nécessaires
    print("\n📁 Création des répertoires...")
    os.makedirs('logs', exist_ok=True)
    os.makedirs('staticfiles', exist_ok=True)
    os.makedirs('media', exist_ok=True)
    print("✅ Répertoires créés")
    
    # 2. Appliquer les migrations
    if not run_command(
        'python manage.py migrate --settings=ecole_moderne.settings_production',
        'Application des migrations de base de données'
    ):
        print("⚠️  Continuons malgré l'erreur de migration...")
    
    # 3. Collecter les fichiers statiques
    run_command(
        'python manage.py collectstatic --noinput --settings=ecole_moderne.settings_production',
        'Collection des fichiers statiques'
    )
    
    # 4. Créer un superutilisateur si nécessaire
    print("\n👤 Vérification du superutilisateur...")
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings_production')
        django.setup()
        from django.contrib.auth.models import User
        
        if not User.objects.filter(is_superuser=True).exists():
            print("Aucun superutilisateur trouvé. Création automatique...")
            User.objects.create_superuser(
                username='admin',
                email='admin@myschoolgn.space',
                password='admin123'
            )
            print("✅ Superutilisateur créé: admin/admin123")
        else:
            print("✅ Superutilisateur existant trouvé")
    except Exception as e:
        print(f"⚠️  Erreur lors de la création du superutilisateur: {e}")
    
    # 5. Initialiser les données de base
    print("\n🏫 Initialisation des données de base...")
    try:
        from ecole_moderne.management.commands.init_multi_tenant import Command as InitCommand
        init_cmd = InitCommand()
        init_cmd.handle()
        print("✅ Données de base initialisées")
    except Exception as e:
        print(f"⚠️  Erreur lors de l'initialisation: {e}")
    
    # 6. Vérifier la configuration
    print("\n🔍 Vérification de la configuration...")
    run_command(
        'python manage.py check --settings=ecole_moderne.settings_production',
        'Vérification de la configuration Django'
    )
    
    print("\n" + "=" * 60)
    print("🎉 Déploiement terminé!")
    print("\n📋 Informations importantes:")
    print("• URL: https://www.myschoolgn.space")
    print("• Admin: https://www.myschoolgn.space/admin/")
    print("• Inscription écoles: https://www.myschoolgn.space/ecole/inscription-complete/")
    print("• Superutilisateur: admin / admin123")
    print("\n⚠️  N'oubliez pas de:")
    print("1. Configurer les variables d'environnement dans .bashrc")
    print("2. Activer le certificat HTTPS")
    print("3. Recharger l'application web")
    print("4. Changer le mot de passe admin par défaut")

if __name__ == '__main__':
    main()
