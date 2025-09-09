# Guide de Configuration PostgreSQL pour École Moderne

Ce guide vous explique comment configurer le projet École Moderne pour utiliser PostgreSQL au lieu de SQLite.

## 📋 Prérequis

1. **PostgreSQL installé** sur votre système
   - Windows: Téléchargez depuis [postgresql.org](https://www.postgresql.org/download/windows/)
   - Ubuntu/Debian: `sudo apt-get install postgresql postgresql-contrib`
   - macOS: `brew install postgresql`

2. **Python et pip** installés
3. **Accès administrateur** à PostgreSQL

## 🚀 Installation et Configuration

### 1. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

Les nouvelles dépendances ajoutées:
- `psycopg2-binary>=2.9.0` - Adaptateur PostgreSQL pour Django
- `python-dotenv>=1.0.0` - Gestion des variables d'environnement

### 2. Configurer les variables d'environnement

1. Copiez le fichier d'exemple:
```bash
cp .env.example .env
```

2. Modifiez le fichier `.env` avec vos paramètres PostgreSQL:
```env
# Configuration de la base de données
DATABASE_ENGINE=postgresql
DATABASE_NAME=ecole_moderne
DATABASE_USER=votre_utilisateur
DATABASE_PASSWORD=votre_mot_de_passe
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

### 3. Créer la base de données PostgreSQL

#### Option A: Création manuelle
```sql
-- Connectez-vous à PostgreSQL en tant qu'administrateur
sudo -u postgres psql

-- Créez l'utilisateur
CREATE USER votre_utilisateur WITH PASSWORD 'votre_mot_de_passe';

-- Créez la base de données
CREATE DATABASE ecole_moderne OWNER votre_utilisateur;

-- Accordez les privilèges
GRANT ALL PRIVILEGES ON DATABASE ecole_moderne TO votre_utilisateur;

-- Quittez
\q
```

#### Option B: Utilisation de la commande Django
```bash
python manage.py setup_postgresql --create-db --migrate
```

## 🔄 Migration depuis SQLite

Si vous avez déjà des données dans SQLite et souhaitez les migrer vers PostgreSQL:

### Migration automatique
```bash
python scripts/migrate_to_postgresql.py
```

### Migration manuelle

1. **Sauvegarder les données SQLite:**
```bash
# Avec SQLite configuré
python manage.py dumpdata --natural-foreign --natural-primary --exclude=contenttypes --exclude=auth.permission --exclude=sessions > backup.json
```

2. **Configurer PostgreSQL** (voir étapes ci-dessus)

3. **Effectuer les migrations:**
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **Restaurer les données:**
```bash
python manage.py loaddata backup.json
```

## 🛠️ Commandes utiles

### Commande de setup PostgreSQL
```bash
# Setup complet avec création de DB et migrations
python manage.py setup_postgresql --create-db --migrate --load-data

# Seulement les migrations
python manage.py setup_postgresql --migrate

# Seulement le test de connexion
python manage.py setup_postgresql
```

### Gestion des migrations
```bash
# Créer de nouvelles migrations
python manage.py makemigrations

# Appliquer les migrations
python manage.py migrate

# Voir l'état des migrations
python manage.py showmigrations
```

### Sauvegardes PostgreSQL
```bash
# Sauvegarder la base
pg_dump -U votre_utilisateur -h localhost ecole_moderne > backup.sql

# Restaurer depuis une sauvegarde
psql -U votre_utilisateur -h localhost ecole_moderne < backup.sql
```

## 🔧 Configuration avancée

### Optimisations PostgreSQL pour Django

Ajoutez ces paramètres dans votre `postgresql.conf`:

```conf
# Optimisations pour Django
shared_preload_libraries = 'pg_stat_statements'
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

### Variables d'environnement complètes

```env
# Django
DJANGO_SECRET_KEY=votre-clé-secrète-très-longue-et-complexe
DJANGO_DEBUG=false

# Base de données
DATABASE_ENGINE=postgresql
DATABASE_NAME=ecole_moderne
DATABASE_USER=ecole_user
DATABASE_PASSWORD=mot_de_passe_sécurisé
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Sécurité
PHONE_VERIFY_TTL_SECONDS=14400

# Twilio (optionnel)
TWILIO_ENABLED=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```

## 🔍 Dépannage

### Erreurs courantes

1. **"FATAL: password authentication failed"**
   - Vérifiez les identifiants dans `.env`
   - Vérifiez la configuration `pg_hba.conf`

2. **"could not connect to server"**
   - Vérifiez que PostgreSQL est démarré
   - Vérifiez l'adresse et le port dans `.env`

3. **"database does not exist"**
   - Créez la base avec `python manage.py setup_postgresql --create-db`

4. **Erreurs de migration**
   - Supprimez les fichiers de migration: `find . -path "*/migrations/*.py" -not -name "__init__.py" -delete`
   - Recréez les migrations: `python manage.py makemigrations`

### Vérification de la configuration

```bash
# Tester la connexion
python manage.py dbshell

# Vérifier les settings Django
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES)"
```

## 📊 Performance et monitoring

### Surveillance des performances
```sql
-- Requêtes les plus lentes
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Taille des tables
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Maintenance régulière
```bash
# Analyser les statistiques
python manage.py dbshell -c "ANALYZE;"

# Nettoyer les données obsolètes
python manage.py dbshell -c "VACUUM ANALYZE;"
```

## 🔒 Sécurité

### Recommandations de sécurité

1. **Utilisateur dédié**: Ne pas utiliser l'utilisateur `postgres` en production
2. **Mot de passe fort**: Utilisez un générateur de mots de passe
3. **Connexions chiffrées**: Configurez SSL pour les connexions distantes
4. **Sauvegardes régulières**: Automatisez les sauvegardes quotidiennes
5. **Monitoring**: Surveillez les connexions et les performances

### Configuration SSL (production)

```env
# Dans .env pour SSL
DATABASE_OPTIONS={"sslmode": "require"}
```

## 📝 Notes importantes

- **Développement**: Vous pouvez continuer à utiliser SQLite en local en définissant `DATABASE_ENGINE=sqlite3`
- **Production**: Utilisez toujours PostgreSQL en production pour de meilleures performances
- **Sauvegardes**: Configurez des sauvegardes automatiques régulières
- **Monitoring**: Surveillez les performances et l'utilisation de la base

## 🆘 Support

En cas de problème:
1. Vérifiez les logs Django: `tail -f logs/security.log`
2. Vérifiez les logs PostgreSQL: `/var/log/postgresql/`
3. Testez la connexion: `python manage.py setup_postgresql`
4. Consultez la documentation Django: [docs.djangoproject.com](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes)
