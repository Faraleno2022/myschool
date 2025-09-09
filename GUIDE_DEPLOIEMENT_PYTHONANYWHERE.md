# Guide de Déploiement - École Moderne sur PythonAnywhere

## 📋 Prérequis

1. **Compte PythonAnywhere** : Créez un compte sur [pythonanywhere.com](https://www.pythonanywhere.com)
2. **Nom d'utilisateur** : `faraleno2022` (configuré dans les fichiers)
3. **Plan recommandé** : Hacker ou supérieur pour MySQL et domaine personnalisé

## 🚀 Étapes de Déploiement

### 1. Préparation des fichiers

Les fichiers suivants ont été créés pour le déploiement :
- `requirements.txt` - Dépendances Python
- `settings_production.py` - Configuration production
- `wsgi_pythonanywhere.py` - Configuration WSGI
- `deploy_pythonanywhere.py` - Script de déploiement
- `.gitignore` - Fichiers à ignorer

### 2. Upload des fichiers

1. Connectez-vous à votre dashboard PythonAnywhere
2. Allez dans l'onglet **Files**
3. Créez le répertoire `/home/faraleno2022/myschool/`
4. Uploadez tous les fichiers du projet dans ce répertoire

### 3. Installation des dépendances

Dans la console Bash de PythonAnywhere :

```bash
cd /home/faraleno2022/myschool
pip3.10 install --user -r requirements.txt
```

### 4. Configuration de la base de données

1. Allez dans l'onglet **Databases**
2. Créez une base MySQL nommée : `faraleno2022$myschool`
3. Notez le mot de passe généré

### 5. Configuration des variables d'environnement

Éditez le fichier `.bashrc` dans votre répertoire home :

```bash
# Variables d'environnement pour École Moderne
export DB_PASSWORD='votre_mot_de_passe_mysql'
export EMAIL_HOST_USER='votre_email@gmail.com'
export EMAIL_HOST_PASSWORD='votre_mot_de_passe_app_gmail'
export DEFAULT_FROM_EMAIL='noreply@ecole-moderne.com'
```

Rechargez les variables :
```bash
source ~/.bashrc
```

### 6. Configuration de l'application web

1. Allez dans l'onglet **Web**
2. Cliquez sur **Add a new web app**
3. Choisissez **Manual configuration** et **Python 3.10**
4. Configurez les paramètres suivants :

#### Source code
```
/home/faraleno2022/myschool
```

#### WSGI configuration file
```
/home/faraleno2022/myschool/wsgi_pythonanywhere.py
```

#### Static files
| URL | Directory |
|-----|-----------|
| `/static/` | `/home/faraleno2022/myschool/staticfiles/` |
| `/media/` | `/home/faraleno2022/myschool/media/` |

### 7. Exécution du script de déploiement

Dans la console :

```bash
cd /home/faraleno2022/myschool
python deploy_pythonanywhere.py
```

### 8. Migrations et configuration finale

```bash
# Application des migrations
python manage.py migrate --settings=ecole_moderne.settings_production

# Collection des fichiers statiques
python manage.py collectstatic --noinput --settings=ecole_moderne.settings_production

# Création d'un superutilisateur
python manage.py createsuperuser --settings=ecole_moderne.settings_production
```

### 9. Redémarrage de l'application

1. Retournez dans l'onglet **Web**
2. Cliquez sur **Reload** pour redémarrer l'application

## 🌐 Accès à l'application

Votre application sera accessible à :
- **URL principale** : https://faraleno2022.pythonanywhere.com
- **Administration** : https://faraleno2022.pythonanywhere.com/admin/
- **Inscription écoles** : https://faraleno2022.pythonanywhere.com/ecole/inscription-complete/

## 🔧 Configuration Email (Gmail)

Pour activer les notifications email :

1. Activez l'authentification à 2 facteurs sur votre compte Gmail
2. Générez un mot de passe d'application :
   - Allez dans **Paramètres Google** → **Sécurité**
   - **Mots de passe des applications**
   - Générez un mot de passe pour "École Moderne"
3. Utilisez ce mot de passe dans `EMAIL_HOST_PASSWORD`

## 🛠️ Dépannage

### Erreur de base de données
- Vérifiez que la base `faraleno2022$myschool` existe
- Vérifiez le mot de passe dans les variables d'environnement

### Erreur de fichiers statiques
```bash
python manage.py collectstatic --clear --noinput --settings=ecole_moderne.settings_production
```

### Erreur de permissions
```bash
chmod +x deploy_pythonanywhere.py
```

### Logs d'erreur
Consultez les logs dans :
- **Error log** : Onglet Web de PythonAnywhere
- **Server log** : `/home/faraleno2022/myschool/logs/django.log`

## 📊 Fonctionnalités disponibles

Après déploiement, votre système École Moderne inclut :

✅ **Inscription d'écoles complète** avec classes et échéances
✅ **Système multi-tenant** sécurisé
✅ **Gestion des élèves** et paiements
✅ **Rapports** et statistiques
✅ **Administration** complète
✅ **Notifications** email automatiques
✅ **Interface** responsive et moderne

## 🔒 Sécurité

Le système est configuré avec :
- HTTPS forcé
- Protection CSRF
- Headers de sécurité
- Sessions sécurisées
- Isolation des données entre écoles

## 📞 Support

En cas de problème :
1. Consultez les logs d'erreur
2. Vérifiez la configuration dans l'onglet Web
3. Testez les connexions base de données et email
4. Redémarrez l'application web

---

**🎉 Félicitations ! Votre système École Moderne est maintenant déployé sur PythonAnywhere !**
