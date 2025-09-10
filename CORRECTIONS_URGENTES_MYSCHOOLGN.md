# 🚨 CORRECTIONS URGENTES - www.myschoolgn.space

## Problèmes Critiques Détectés

### 1. **Chemin Source Code - INCORRECT**
**Actuel :** `/home/myschoolgn/myschool` ❌
**Correct :** `/home/myschoolgn/monécole` ✅

### 2. **Chemins Fichiers Statiques - PARTIELLEMENT INCORRECT**
**Actuel :**
- `/static/` → `/home/myschoolgn/monécole/static` ❌
- `/media/` → `/home/myschoolgn/monécole/media/` ✅

**Correct :**
- `/static/` → `/home/myschoolgn/monécole/staticfiles/` ✅
- `/media/` → `/home/myschoolgn/monécole/media/` ✅

## 🔧 Actions Immédiates dans PythonAnywhere

### Étape 1: Corriger le Code Source
Dans l'onglet **Web** → **Code** :
```
Source code: /home/myschoolgn/monécole
```

### Étape 2: Corriger les Fichiers Statiques
Dans l'onglet **Web** → **Static files** :

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/myschoolgn/monécole/staticfiles/` |
| `/media/` | `/home/myschoolgn/monécole/media/` |

### Étape 3: Vérifier le Fichier WSGI
Le fichier `/var/www/www_myschoolgn_space_wsgi.py` doit contenir :

```python
import os
import sys

# Chemin du projet
path = '/home/myschoolgn/monécole'
if path not in sys.path:
    sys.path.insert(0, path)

# Settings de production
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings_production')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Étape 4: Créer les Répertoires Manquants
Dans la console Bash :
```bash
cd /home/myschoolgn/monécole
mkdir -p staticfiles
mkdir -p media
mkdir -p logs
```

### Étape 5: Installer les Dépendances
```bash
cd /home/myschoolgn/monécole
pip3.11 install --user -r requirements.txt
```

### Étape 6: Configurer la Base de Données
Créez une base MySQL : `myschoolgn$myschool`

### Étape 7: Variables d'Environnement
Éditez `~/.bashrc` :
```bash
export DB_PASSWORD='votre_mot_de_passe_mysql'
export EMAIL_HOST_USER='votre_email@gmail.com'
export EMAIL_HOST_PASSWORD='votre_mot_de_passe_app_gmail'
export DEFAULT_FROM_EMAIL='noreply@myschoolgn.space'
```

Puis :
```bash
source ~/.bashrc
```

### Étape 8: Déploiement
```bash
cd /home/myschoolgn/monécole
python deploy_myschoolgn.py
```

### Étape 9: Activer HTTPS
Dans l'onglet **Web** → **Security** :
1. Cliquez "Get certificate from Let's Encrypt"
2. Activez "Force HTTPS"

### Étape 10: Recharger l'Application
Cliquez sur **Reload** dans l'onglet Web

## ⚠️ Points Critiques

1. **Le répertoire source DOIT être `/home/myschoolgn/monécole`**
2. **Les fichiers statiques DOIVENT pointer vers `staticfiles/` pas `static/`**
3. **Toujours recharger après chaque modification**

## 🎯 Résultat Attendu

Après corrections :
- ✅ https://www.myschoolgn.space (site principal)
- ✅ https://www.myschoolgn.space/admin/ (administration)
- ✅ https://www.myschoolgn.space/ecole/inscription-complete/ (inscription écoles)

## 📞 En Cas de Problème

1. Vérifiez les logs : `www.myschoolgn.space.error.log`
2. Testez la connexion DB
3. Vérifiez que tous les répertoires existent
4. Rechargez l'application après chaque modification
