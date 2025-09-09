#!/usr/bin/env python
"""
Script pour vérifier l'installation PostgreSQL et préparer la configuration
Usage: python check_postgresql.py
"""

import subprocess
import sys
import os
from pathlib import Path

def check_postgresql_installation():
    """Vérifier si PostgreSQL est installé"""
    print("🔍 Vérification de l'installation PostgreSQL...")
    
    # Chemins possibles pour PostgreSQL sur Windows
    possible_paths = [
        r"C:\Program Files\PostgreSQL\16\bin",
        r"C:\Program Files\PostgreSQL\15\bin",
        r"C:\Program Files\PostgreSQL\14\bin",
        r"C:\Program Files (x86)\PostgreSQL\16\bin",
        r"C:\Program Files (x86)\PostgreSQL\15\bin",
    ]
    
    # Vérifier psql dans le PATH
    try:
        result = subprocess.run(['psql', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ PostgreSQL trouvé dans le PATH: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Vérifier dans les chemins possibles
    for path in possible_paths:
        psql_path = Path(path) / "psql.exe"
        if psql_path.exists():
            print(f"✅ PostgreSQL trouvé: {psql_path}")
            print(f"   Ajoutez {path} à votre PATH pour utiliser psql")
            return True
    
    print("❌ PostgreSQL non trouvé")
    return False

def check_postgresql_service():
    """Vérifier si le service PostgreSQL fonctionne"""
    print("🔍 Vérification du service PostgreSQL...")
    
    try:
        result = subprocess.run([
            'sc', 'query', 'postgresql-x64-16'
        ], capture_output=True, text=True, timeout=10)
        
        if 'RUNNING' in result.stdout:
            print("✅ Service PostgreSQL en cours d'exécution")
            return True
        elif 'STOPPED' in result.stdout:
            print("⚠️  Service PostgreSQL arrêté")
            print("   Démarrez-le avec: net start postgresql-x64-16")
            return False
        else:
            # Essayer d'autres noms de service
            for service_name in ['postgresql-x64-15', 'postgresql-x64-14', 'PostgreSQL']:
                result = subprocess.run([
                    'sc', 'query', service_name
                ], capture_output=True, text=True, timeout=10)
                
                if 'RUNNING' in result.stdout:
                    print(f"✅ Service PostgreSQL ({service_name}) en cours d'exécution")
                    return True
            
            print("❌ Service PostgreSQL non trouvé ou arrêté")
            return False
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Impossible de vérifier le service PostgreSQL")
        return False

def test_connection():
    """Tester la connexion à PostgreSQL"""
    print("🔍 Test de connexion PostgreSQL...")
    
    try:
        # Essayer de se connecter à la base postgres par défaut
        result = subprocess.run([
            'psql', '-h', 'localhost', '-p', '5432', '-U', 'postgres', 
            '-d', 'postgres', '-c', 'SELECT version();'
        ], capture_output=True, text=True, timeout=15, input='\n')
        
        if result.returncode == 0:
            print("✅ Connexion PostgreSQL réussie")
            return True
        else:
            print(f"❌ Erreur de connexion: {result.stderr}")
            return False
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Impossible de tester la connexion")
        return False

def show_configuration_template():
    """Afficher le template de configuration .env"""
    print("\n" + "="*50)
    print("📝 CONFIGURATION POUR VOTRE PROJET")
    print("="*50)
    
    print("\nModifiez votre fichier .env avec ces paramètres :")
    print("""
# Configuration PostgreSQL
DATABASE_ENGINE=postgresql
DATABASE_NAME=ecole_moderne
DATABASE_USER=postgres
DATABASE_PASSWORD=VotreMotDePasse
DATABASE_HOST=localhost
DATABASE_PORT=5432
""")
    
    print("Remplacez 'VotreMotDePasse' par le mot de passe que vous avez défini lors de l'installation.")

def show_next_steps():
    """Afficher les prochaines étapes"""
    print("\n" + "="*50)
    print("🚀 PROCHAINES ÉTAPES")
    print("="*50)
    
    print("\n1. Si PostgreSQL n'est pas installé :")
    print("   - Téléchargez depuis: https://www.postgresql.org/download/windows/")
    print("   - Installez avec le mot de passe: EcoleModerne2024!")
    print("   - Redémarrez votre terminal après installation")
    
    print("\n2. Une fois PostgreSQL installé :")
    print("   - Modifiez votre fichier .env (voir configuration ci-dessus)")
    print("   - Exécutez: python setup_postgresql.py --all")
    
    print("\n3. Pour vérifier à nouveau :")
    print("   - Exécutez: python check_postgresql.py")

def main():
    print("🔧 Vérification PostgreSQL pour École Moderne")
    print("="*50)
    
    # Vérifications
    installation_ok = check_postgresql_installation()
    service_ok = False
    connection_ok = False
    
    if installation_ok:
        service_ok = check_postgresql_service()
        if service_ok:
            connection_ok = test_connection()
    
    # Résumé
    print("\n" + "="*50)
    print("📊 RÉSUMÉ")
    print("="*50)
    print(f"Installation PostgreSQL: {'✅' if installation_ok else '❌'}")
    print(f"Service PostgreSQL:      {'✅' if service_ok else '❌'}")
    print(f"Connexion PostgreSQL:    {'✅' if connection_ok else '❌'}")
    
    if installation_ok and service_ok and connection_ok:
        print("\n🎉 PostgreSQL est prêt à être utilisé !")
        show_configuration_template()
        print("\nExécutez maintenant: python setup_postgresql.py --all")
    else:
        show_next_steps()
    
    return installation_ok and service_ok and connection_ok

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
