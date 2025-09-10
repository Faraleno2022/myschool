# Configuration pour www.myschoolgn.space

## 🔧 Corrections Nécessaires dans PythonAnywhere

### 1. **Fichiers Statiques - URGENT**
Vos chemins actuels sont incorrects. Corrigez dans l'onglet **Web** :

| URL | Répertoire Correct |
|-----|-------------------|
| `/static/` | `/home/myschoolgn/monécole/staticfiles/` |
| `/media/` | `/home/myschoolgn/monécole/media/` |

**Problème détecté :** 
- ❌ `/home/myschoolgn/myschool/static` (incorrect)
- ❌ `/home/monécolegn/monécole/media` (incorrect)

### 2. **Fichier WSGI - URGENT**
Remplacez le contenu de `/var/www/www_myschoolgn_space_wsgi.py` par :

```python
"""
WSGI config pour PythonAnywhere - École Moderne
"""
import os
import sys

# Ajouter le chemin du projet
path = '/home/myschoolgn/monécole'
if path not in sys.path:
    sys.path.insert(0, path)

# Utiliser les settings de production
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings_production')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 3. **Base de Données MySQL**
Créez une base de données nommée : `myschoolgn$myschool`

### 4. **Variables d'Environnement**
Ajoutez dans votre fichier `.bashrc` :

```bash
# Variables d'environnement pour École Moderne
export DB_PASSWORD='votre_mot_de_passe_mysql'
export EMAIL_HOST_USER='votre_email@gmail.com'
export EMAIL_HOST_PASSWORD='votre_mot_de_passe_app_gmail'
export DEFAULT_FROM_EMAIL='noreply@myschoolgn.space'
```

Puis rechargez :
```bash
source ~/.bashrc
```

## 🚀 Étapes de Déploiement

### 1. Upload des Fichiers
Uploadez tous les fichiers du projet dans : `/home/myschoolgn/monécole/`

### 2. Installation des Dépendances
```bash
cd /home/myschoolgn/monécole
pip3.11 install --user -r requirements.txt
```

### 3. Exécution du Script de Déploiement
```bash
cd /home/myschoolgn/monécole
python deploy_myschoolgn.py
```

### 4. Configuration Finale
1. **Migrations** :
```bash
python manage.py migrate --settings=ecole_moderne.settings_production
```

2. **Fichiers statiques** :
```bash
python manage.py collectstatic --noinput --settings=ecole_moderne.settings_production
```

3. **Superutilisateur** :
```bash
python manage.py createsuperuser --settings=ecole_moderne.settings_production
```

## 🔒 Configuration HTTPS

### Certificat SSL Gratuit
1. Dans l'onglet **Web** → **Security**
2. Cliquez sur **Get certificate from Let's Encrypt**
3. Activez **Force HTTPS**

### Configuration de Sécurité
Vos settings de production incluent déjà :
- ✅ HTTPS forcé
- ✅ Headers de sécurité
- ✅ Protection CSRF
- ✅ Sessions sécurisées

## 🌐 URLs d'Accès

Après configuration :
- **Site principal** : https://www.myschoolgn.space
- **Administration** : https://www.myschoolgn.space/admin/
- **Inscription écoles** : https://www.myschoolgn.space/ecole/inscription-complete/

## 🛠️ Dépannage

### Erreur 500 - Internal Server Error
1. Vérifiez les logs : `www.myschoolgn.space.error.log`
2. Vérifiez les chemins des fichiers statiques
3. Vérifiez la connexion à la base de données

### Fichiers statiques non chargés
1. Vérifiez les mappages dans l'onglet **Web**
2. Exécutez `collectstatic` à nouveau
3. Rechargez l'application web

### Erreur de base de données
1. Vérifiez que `myschoolgn$myschool` existe
2. Vérifiez le mot de passe dans les variables d'environnement
3. Testez la connexion MySQL

## 📋 Checklist de Déploiement

- [ ] Fichiers uploadés dans `/home/myschoolgn/monécole/`
- [ ] Base de données `myschoolgn$myschool` créée
- [ ] Variables d'environnement configurées
- [ ] Dépendances installées
- [ ] Fichier WSGI corrigé
- [ ] Chemins statiques corrigés
- [ ] Migrations appliquées
- [ ] Fichiers statiques collectés
- [ ] Certificat HTTPS activé
- [ ] Application rechargée

## 🎯 Fonctionnalités Disponibles

Après déploiement réussi :
- ✅ Système multi-tenant sécurisé
- ✅ Inscription d'écoles avec workflow d'approbation
- ✅ Gestion complète des élèves et paiements
- ✅ Rapports et statistiques
- ✅ Documents PDF personnalisés
- ✅ Notifications email automatiques
- ✅ Interface responsive et moderne

---

**🚨 Actions Immédiates Requises :**
1. Corriger les chemins des fichiers statiques
2. Remplacer le fichier WSGI
3. Recharger l'application web
4. Activer le certificat HTTPS
