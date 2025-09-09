# Guide de Démarrage Rapide - Système Multi-Tenant

## 🚀 Mise en route

### 1. Vérification des prérequis
```bash
# Vérifier Python et Django
python --version  # Python 3.8+
python manage.py --version  # Django 5.2.3

# Vérifier les dépendances
pip install -r requirements.txt
```

### 2. Configuration de la base de données
```bash
# Appliquer les migrations
python manage.py makemigrations
python manage.py migrate

# Créer un super-utilisateur
python manage.py createsuperuser
```

### 3. Initialisation du système multi-tenant
```bash
# Test du système
python test_multi_tenant.py

# Initialisation avec données de base
python manage.py init_multi_tenant --create-demo-schools --create-templates --assign-existing-users
```

### 4. Démarrage du serveur
```bash
python manage.py runserver
```

## 🏫 Première utilisation

### Connexion Super-Admin
1. Accédez à `http://127.0.0.1:8000/`
2. Connectez-vous avec votre compte super-utilisateur
3. Utilisez le sélecteur d'école en haut de page

### Inscription d'une nouvelle école
1. Accédez à `http://127.0.0.1:8000/ecole/inscription/`
2. Remplissez le formulaire d'inscription
3. En tant que super-admin, traitez la demande via "Multi-Écoles > Demandes d'inscription"

### Gestion des utilisateurs
1. Menu "Multi-Écoles > Gestion utilisateurs"
2. Créez des comptes pour chaque école
3. Assignez les rôles et permissions appropriés

## 🔧 Configuration avancée

### Personnalisation par école
- **Logos** : Uploadez via l'admin Django
- **Templates PDF** : Menu école > Personnaliser documents
- **Configuration** : Préfixes, notifications, etc.

### Permissions granulaires
- `peut_valider_paiements`
- `peut_valider_depenses`
- `peut_generer_rapports`
- `peut_gerer_utilisateurs`

## 📋 Workflows principaux

### Workflow d'inscription école
1. **Demande** → Formulaire public
2. **Révision** → Super-admin vérifie
3. **Approbation** → Création automatique école + admin
4. **Notification** → Email avec identifiants

### Workflow utilisateur
1. **Connexion** → Authentification
2. **Sélection école** → Middleware automatique
3. **Permissions** → Vérification par rôle
4. **Accès données** → Filtrage par école

## 🛠️ Dépannage

### Problèmes courants

**Erreur "Aucune école assignée"**
```bash
# Vérifier les profils utilisateurs
python manage.py shell
>>> from utilisateurs.models import Profil
>>> Profil.objects.filter(ecole__isnull=True)
```

**Middleware non fonctionnel**
- Vérifiez `MIDDLEWARE` dans `settings.py`
- Ordre important : après `AuthenticationMiddleware`

**Permissions insuffisantes**
- Vérifiez le rôle dans le profil utilisateur
- Contrôlez les permissions granulaires

### Commandes utiles
```bash
# Lister les écoles
python manage.py shell -c "from eleves.models import Ecole; [print(e) for e in Ecole.objects.all()]"

# Réinitialiser les sessions
python manage.py clearsessions

# Vérifier la configuration
python manage.py check
```

## 📊 Monitoring

### Logs importants
- `logs/security.log` : Événements de sécurité
- Console Django : Erreurs de middleware
- Admin Django : Journal des activités

### Métriques à surveiller
- Nombre d'écoles actives
- Utilisateurs par école
- Demandes d'inscription en attente
- Sessions actives

## 🔒 Sécurité

### Bonnes pratiques
- Mots de passe forts obligatoires
- Sessions avec timeout (30 min)
- Logs de sécurité activés
- Isolation stricte des données

### Audit
- Journal des activités utilisateurs
- Traçabilité des modifications
- Alertes sur actions sensibles

## 🚀 Mise en production

### Configuration production
```python
# settings.py
DEBUG = False
ALLOWED_HOSTS = ['votre-domaine.com']
DATABASE_ENGINE = 'postgresql'  # Recommandé
```

### Optimisations
- Cache Redis/Memcached
- Serveur web (Nginx + Gunicorn)
- Base de données PostgreSQL
- Sauvegarde automatique

## 📞 Support

### Ressources
- `README_MULTI_TENANT.md` : Documentation complète
- `test_multi_tenant.py` : Tests de validation
- Admin Django : Interface d'administration

### Commandes de diagnostic
```bash
# Test complet du système
python test_multi_tenant.py

# Vérification de la configuration
python manage.py check --deploy

# État de la base de données
python manage.py showmigrations
```
