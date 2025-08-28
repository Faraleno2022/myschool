# École Moderne HADJA KANFING DIANÉ – Système de Gestion

Application Django pour la gestion scolaire (élèves, paiements, salaires, rapports) avec séparation par école (Sonfonia/Somayah), contrôles d'accès, et exports (PDF/CSV).

## ✨ Nouvelles fonctionnalités (Août 2025)

### 🧾 Système de remises sur reçus PDF
- **Affichage des remises** appliquées directement sur les reçus de paiement PDF
- **Note explicative** claire pour les parents/élèves
- **Intégration complète** dans la vue détail paiement HTML

### 🎓 Système de matricules robuste
- **Codification officielle** : GA, MPS/MMS/MGS, PN1-6, CN7-10, L11SL/SSI/SSII, L12SS/SM/SE, TSS/TSM/TSE
- **Génération automatique** format CODE-### (ex: PN3-042, L11SL-007)
- **Support des variantes** d'écriture (1ère/1ere/première, etc.)
- **Scripts de maintenance** pour nettoyer les matricules existants

### 📊 Rapports financiers enrichis
- **Montant original** (avant remises)
- **Total des remises accordées**
- **Montant net encaissé**
- **Intégré** dans tous les rapports (journalier, hebdomadaire, mensuel, annuel)

### 🛠️ Scripts utilitaires
- `scripts/fix_matricules_duplicates.py` : Nettoyage matricules vides/dupliqués
- `scripts/test_matricule_generation.py` : Tests de validation (67 cas de test)

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

### Endpoints paiements (Août 2025)
- Export Excel par période:
  - `GET /paiements/export/periode/excel/?du=YYYY-MM-DD&au=YYYY-MM-DD&statut=VALIDE|EN_ATTENTE` → Fichier `.xlsx`
- Rapports:
  - `GET /paiements/rapport/retards/` → HTML (ou JSON fallback)
  - `GET /paiements/rapport/encaissements/?du=&au=` → HTML (ou JSON fallback)
- API JSON:
  - `GET /paiements/api/paiements/?q=&statut=&limit=` → `{results: [...]}`
  - `GET /paiements/api/paiements/<id>/` → Détails d’un paiement
- Remises:
  - `POST/GET /paiements/remise/<paiement_id>/annuler/` → Annule toutes les remises du paiement
  - `POST/GET /paiements/remise/<paiement_id>/annuler/<remise_id>/` → Annule une remise spécifique

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
