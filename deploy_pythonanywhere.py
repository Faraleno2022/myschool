#!/usr/bin/env python3
"""
Script de déploiement pour PythonAnywhere
Automatise les étapes de déploiement du projet École Moderne
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Exécute une commande et affiche le résultat"""
    print(f"\n🔄 {description}...")
    print(f"Commande: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - Succès")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Erreur")
        print(f"Error: {e.stderr}")
        return False

def main():
    """Fonction principale de déploiement"""
    print("🚀 Déploiement École Moderne sur PythonAnywhere")
    print("=" * 50)
    
    # Vérifier que nous sommes dans le bon répertoire
    if not os.path.exists('manage.py'):
        print("❌ Erreur: manage.py non trouvé. Exécutez ce script depuis la racine du projet.")
        sys.exit(1)
    
    # 1. Collecter les fichiers statiques
    print("\n📁 Étape 1: Collection des fichiers statiques")
    if not run_command(
        "python manage.py collectstatic --noinput --settings=ecole_moderne.settings_production",
        "Collection des fichiers statiques"
    ):
        print("⚠️ Attention: Erreur lors de la collection des fichiers statiques")
    
    # 2. Vérifier les migrations
    print("\n🔄 Étape 2: Vérification des migrations")
    run_command(
        "python manage.py showmigrations --settings=ecole_moderne.settings_production",
        "Affichage des migrations"
    )
    
    # 3. Appliquer les migrations (si nécessaire)
    print("\n📊 Étape 3: Application des migrations")
    if not run_command(
        "python manage.py migrate --settings=ecole_moderne.settings_production",
        "Application des migrations"
    ):
        print("⚠️ Attention: Erreur lors de l'application des migrations")
    
    # 4. Vérifier la configuration
    print("\n🔍 Étape 4: Vérification de la configuration")
    run_command(
        "python manage.py check --settings=ecole_moderne.settings_production",
        "Vérification de la configuration Django"
    )
    
    # 5. Créer un superutilisateur (optionnel)
    print("\n👤 Étape 5: Création d'un superutilisateur (optionnel)")
    print("Pour créer un superutilisateur, exécutez:")
    print("python manage.py createsuperuser --settings=ecole_moderne.settings_production")
    
    # 6. Instructions finales
    print("\n" + "=" * 50)
    print("🎉 Déploiement terminé!")
    print("\n📋 Instructions pour PythonAnywhere:")
    print("1. Uploadez tous les fichiers du projet dans /home/faraleno2022/myschool/")
    print("2. Installez les dépendances: pip3.10 install --user -r requirements.txt")
    print("3. Configurez la base de données MySQL dans l'onglet 'Databases'")
    print("4. Configurez l'application web:")
    print("   - Source code: /home/faraleno2022/myschool")
    print("   - WSGI file: /home/faraleno2022/myschool/wsgi_pythonanywhere.py")
    print("   - Static files: /static/ -> /home/faraleno2022/myschool/staticfiles/")
    print("   - Media files: /media/ -> /home/faraleno2022/myschool/media/")
    print("5. Définissez les variables d'environnement dans l'onglet 'Files' -> .bashrc:")
    print("   export DB_PASSWORD='votre_mot_de_passe_mysql'")
    print("   export EMAIL_HOST_USER='votre_email'")
    print("   export EMAIL_HOST_PASSWORD='votre_mot_de_passe_email'")
    print("   export DEFAULT_FROM_EMAIL='noreply@votredomaine.com'")
    print("\n🌐 Votre site sera accessible à: https://faraleno2022.pythonanywhere.com")

if __name__ == "__main__":
    main()
