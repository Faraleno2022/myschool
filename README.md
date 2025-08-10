# École Moderne HADJA KANFING DIANÉ – Système de Gestion

Application Django pour la gestion scolaire (élèves, paiements, salaires, rapports) avec séparation par école (Sonfonia/Somayah), contrôles d'accès, et exports (PDF/CSV).

## Prérequis
- Python 3.10+
- Pip
- Virtualenv (recommandé)

## Installation locale
```bash
# 1) Créer un environnement virtuel
python -m venv .venv

# 2) Activer l'environnement
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# 3) Installer les dépendances
pip install -r requirements.txt

# 4) Variables d'environnement (optionnel)
# set DJANGO_DEBUG=1

# 5) Migrations
python manage.py migrate

# 6) Créer un superuser
python manage.py createsuperuser

# 7) Lancer le serveur
python manage.py runserver
```

## Comptes et accès
- Administrateur: accès à tous les modules (dont Rapports)
- Comptable par école: accès restreint aux données de son école
- Page de connexion: `/utilisateurs/login/` (préserve `next`)

## Exports et rapports
- Rapports PDF avec logo + filigrane, orientation paysage
- Dépenses agrégées globalement (pas de double comptage)
- Section "Dépenses globales" visible dans les rapports annuels/mensuels
- Boutons CSV/PDF dans enseignants, états de salaire, rapports, statistiques élèves

## Déploiement Git (GitHub)
```bash
# Initialiser le dépôt
git init

# Ajouter les fichiers
git add .

# Premier commit
git commit -m "Initial commit: Django SMS + rapports"

# Ajouter l'origine (remplacer par votre URL)
git remote add origin https://github.com/<USER>/<REPO>.git

# Pousser la branche principale
git branch -M main
git push -u origin main
```

## Déploiement sur PythonAnywhere
1. Créez un compte PythonAnywhere et uploadez votre dépôt (via Git ou upload ZIP)
2. Dans Web > Add a new web app > Manual configuration (Python 3.10+)
3. Créez/activez un virtualenv et installez `requirements.txt`
4. WSGI file: pointez vers `ecole_moderne.wsgi:application`
5. Variables d'environnement (si besoin): DJANGO_SETTINGS_MODULE=`ecole_moderne.settings`
6. Static files:
   - URL: `/static/` → dossier collecté (ex: `/home/<user>/<repo>/static_collected/`)
   - Commande: `python manage.py collectstatic --noinput`
7. Media files:
   - URL: `/media/` → dossier `media/`
8. Reload l'app depuis l'onglet Web

## Collecte des statiques en production
```bash
python manage.py collectstatic --noinput
```

## Notes
- Devise par défaut: GNF
- Contexte utilisateur (école/profil/admin) exposé via context processor
- Accès Rapports réservé à l'administrateur (backend + frontend)

## Mise à jour des dépendances
```bash
# Après avoir installé/ajouté des paquets, regénérer le fichier:
pip freeze > requirements.txt
```

## Astuces Git
```bash
# Ajouter tous les changements
git add -A

# Committer avec un message
git commit -m "Message clair: ce qui a changé"

# Pousser sur la branche principale
git push origin main
```

## Détails PythonAnywhere (exemple)
1) Web > Add a new web app > Manual configuration (Python 3.10+)
2) Virtualenv (Console Bash):
```bash
mkvirtualenv --python=/usr/bin/python3.10 env
pip install -r /home/<user>/<repo>/requirements.txt
```
3) WSGI file (Web > WSGI configuration file):
   - Ajoutez la racine du projet au `sys.path`
   - Importez l'application WSGI:
```python
import sys
path = '/home/<user>/<repo>'
if path not in sys.path:
    sys.path.append(path)

from django.core.wsgi import get_wsgi_application
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PROJET.settings')  # Remplacer PROJET
application = get_wsgi_application()
```
4) Variables d'environnement (Web > Environment):
   - `DJANGO_SETTINGS_MODULE=PROJET.settings` (adapter)
   - Clés/Secrets via variables (ne pas committer dans Git)
5) Static files:
   - URL: `/static/` → dossier cible, ex: `/home/<user>/<repo>/static_collected/`
   - Run: `python manage.py collectstatic --noinput`
6) Media files:
   - URL: `/media/` → dossier `/home/<user>/<repo>/media/`
7) Reload l'app depuis l'onglet Web.
