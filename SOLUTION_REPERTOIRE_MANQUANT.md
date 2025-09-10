# 🚨 PROBLÈME CRITIQUE - Répertoire manquant

## Problème Identifié
**Le répertoire `/home/myschoolgn/monécole` n'existe pas sur PythonAnywhere**

## 🔧 Solution Immédiate

### Étape 1: Créer la Structure de Répertoires
Dans la console Bash de PythonAnywhere :

```bash
# Créer le répertoire principal
mkdir -p /home/myschoolgn/monécole

# Créer les sous-répertoires nécessaires
cd /home/myschoolgn/monécole
mkdir -p staticfiles
mkdir -p media
mkdir -p logs
mkdir -p templates
mkdir -p static
```

### Étape 2: Uploader les Fichiers du Projet
Vous devez uploader TOUS les fichiers de votre projet local vers `/home/myschoolgn/monécole/`

**Méthodes d'upload :**

#### Option A: Via l'interface Web Files
1. Allez dans l'onglet **Files** de PythonAnywhere
2. Naviguez vers `/home/myschoolgn/monécole/`
3. Uploadez tous les fichiers du projet un par un

#### Option B: Via Git (Recommandé)
```bash
cd /home/myschoolgn/
git clone https://github.com/votre-username/votre-repo.git monécole
```

#### Option C: Via ZIP
1. Créez un ZIP de votre projet local
2. Uploadez le ZIP dans `/home/myschoolgn/`
3. Extrayez avec : `unzip votre-projet.zip -d monécole`

### Étape 3: Corriger la Configuration PythonAnywhere

Une fois les fichiers uploadés, corrigez dans l'onglet **Web** :

**Static Files :**
```
URL: /static/
Directory: /home/myschoolgn/monécole/staticfiles/

URL: /media/
Directory: /home/myschoolgn/monécole/media/
```

**Source Code :**
```
/home/myschoolgn/monécole
```

### Étape 4: Installation et Configuration
```bash
cd /home/myschoolgn/monécole

# Installer les dépendances
pip3.11 install --user -r requirements.txt

# Créer la base de données MySQL
# (via l'interface PythonAnywhere : myschoolgn$myschool)

# Configurer les variables d'environnement
echo 'export DB_PASSWORD="votre_mot_de_passe_mysql"' >> ~/.bashrc
echo 'export EMAIL_HOST_USER="votre_email@gmail.com"' >> ~/.bashrc
echo 'export EMAIL_HOST_PASSWORD="votre_mot_de_passe_app"' >> ~/.bashrc
echo 'export DEFAULT_FROM_EMAIL="noreply@myschoolgn.space"' >> ~/.bashrc
source ~/.bashrc

# Appliquer les migrations
python manage.py migrate --settings=ecole_moderne.settings_production

# Collecter les fichiers statiques
python manage.py collectstatic --noinput --settings=ecole_moderne.settings_production

# Créer un superutilisateur
python manage.py createsuperuser --settings=ecole_moderne.settings_production
```

### Étape 5: Fichier WSGI
Vérifiez que `/var/www/www_myschoolgn_space_wsgi.py` contient :

```python
import os
import sys

path = '/home/myschoolgn/monécole'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings_production')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Étape 6: Recharger l'Application
Cliquez sur **Reload** dans l'onglet Web

## 📋 Checklist de Vérification

- [ ] Répertoire `/home/myschoolgn/monécole` créé
- [ ] Tous les fichiers du projet uploadés
- [ ] Dépendances installées
- [ ] Base de données MySQL créée
- [ ] Variables d'environnement configurées
- [ ] Migrations appliquées
- [ ] Fichiers statiques collectés
- [ ] Configuration Web mise à jour
- [ ] Application rechargée

## 🎯 Résultat Attendu

Après ces étapes :
- ✅ https://www.myschoolgn.space (fonctionnel)
- ✅ Fichiers statiques chargés correctement
- ✅ Base de données opérationnelle

## ⚠️ Points Critiques

1. **TOUS les fichiers du projet doivent être uploadés**
2. **Le répertoire doit s'appeler exactement `monécole`**
3. **Toujours recharger après modification**
