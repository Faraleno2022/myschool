# Système Multi-Tenant - École Moderne

## Vue d'ensemble

Le système École Moderne a été transformé en plateforme multi-tenant permettant à plusieurs écoles de gérer leurs données de manière indépendante et sécurisée sur une seule instance de l'application.

## Architecture Multi-Tenant

### Modèles principaux

1. **Ecole** (`eleves/models.py`)
   - Modèle central représentant chaque établissement
   - Champs : nom, type, adresse, contact, directeur, etc.
   - Statut : ACTIVE, SUSPENDUE, EN_ATTENTE, FERMEE

2. **Profil** (`utilisateurs/models.py`)
   - Extension du modèle User Django
   - Lié à une école spécifique via ForeignKey
   - Rôles : ADMIN, DIRECTEUR, COMPTABLE, SECRETAIRE, ENSEIGNANT, SURVEILLANT
   - Permissions granulaires par utilisateur

3. **DemandeInscriptionEcole** (`inscription_ecoles/models.py`)
   - Gestion des demandes d'inscription de nouvelles écoles
   - Workflow d'approbation par les super-admins

### Middleware Multi-Tenant

1. **EcoleSelectionMiddleware**
   - Gère la sélection d'école pour chaque requête
   - Super-admins : sélection via session
   - Utilisateurs normaux : école assignée dans leur profil

2. **PermissionEcoleMiddleware**
   - Vérifie les permissions spécifiques à l'école
   - Empêche l'accès inter-écoles non autorisé

3. **EcoleContextMiddleware**
   - Ajoute le contexte école aux templates
   - Fournit la liste des écoles disponibles pour les super-admins

## Fonctionnalités

### Pour les Super-Administrateurs
- Vue globale de toutes les écoles
- Sélecteur d'école dynamique
- Gestion des demandes d'inscription
- Administration des utilisateurs multi-écoles
- Accès aux données de toutes les écoles

### Pour les Administrateurs d'École
- Gestion complète de leur école uniquement
- Création et gestion des utilisateurs de leur école
- Configuration personnalisée (logos, templates, etc.)
- Rapports et statistiques de leur établissement

### Pour les Utilisateurs Standard
- Accès limité aux données de leur école
- Permissions granulaires selon leur rôle
- Interface personnalisée avec les informations de leur école

## Installation et Configuration

### 1. Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Création du Super-Administrateur
```bash
python manage.py createsuperuser
```

### 3. Configuration des Middlewares
Les middlewares sont déjà configurés dans `settings.py` :
- `EcoleSelectionMiddleware`
- `PermissionEcoleMiddleware` 
- `EcoleContextMiddleware`

## Utilisation

### Inscription d'une Nouvelle École

1. **Demande publique** : `/ecole/inscription/`
   - Formulaire complet avec informations école et demandeur
   - Upload de documents (logo, autorisation)
   - Statut initial : EN_ATTENTE

2. **Traitement par Super-Admin** : `/ecole/admin/demandes/`
   - Révision des demandes
   - Approbation ou rejet avec motif
   - Création automatique de l'école et du compte admin

3. **Notification**
   - Email automatique avec identifiants de connexion
   - Mot de passe temporaire à changer

### Gestion des Utilisateurs

#### Création d'Utilisateurs par École
- Super-admins : peuvent créer des utilisateurs pour toute école
- Admins d'école : peuvent créer des utilisateurs pour leur école uniquement
- Rôles et permissions configurables

#### Permissions Granulaires
- `peut_valider_paiements`
- `peut_valider_depenses` 
- `peut_generer_rapports`
- `peut_gerer_utilisateurs`
- Permissions CRUD détaillées par module

### Sélection d'École (Super-Admins)

Interface de sélection disponible sur toutes les pages :
- Mode global : toutes les écoles
- Mode école spécifique : données d'une école uniquement
- Changement dynamique via formulaire

## Sécurité

### Isolation des Données
- Chaque école ne peut accéder qu'à ses propres données
- Middleware de vérification des permissions
- Filtrage automatique par école dans les vues

### Authentification et Autorisation
- Système de rôles hiérarchiques
- Permissions granulaires par fonctionnalité
- Session sécurisée avec timeout

### Audit et Logs
- Journal des activités utilisateurs
- Traçabilité des actions sensibles
- Logs de sécurité séparés

## Templates et Interface

### Composants Multi-Tenant
- `components/ecole_selector.html` : Sélecteur d'école
- Affichage conditionnel selon le contexte
- Personnalisation par école (logos, couleurs)

### Pages Spécialisées
- Tableau de bord par école
- Gestion des utilisateurs filtrée
- Configuration personnalisée
- Templates de documents PDF

## API et Extensions

### Points d'Extension
- Middleware personnalisés
- Décorateurs de permissions
- Mixins pour vues basées sur les classes

### Décorateurs Disponibles
- `@ecole_required`
- `@role_required('ADMIN', 'DIRECTEUR')`
- `@permission_required('peut_valider_paiements')`
- `@same_ecole_required`

## Maintenance

### Commandes de Gestion
```bash
# Lister les écoles
python manage.py shell -c "from eleves.models import Ecole; print(Ecole.objects.all())"

# Créer un utilisateur pour une école
python manage.py shell -c "from utilisateurs.models import Profil; # voir script"

# Nettoyer les sessions expirées
python manage.py clearsessions
```

### Monitoring
- Surveillance des connexions par école
- Statistiques d'utilisation
- Alertes de sécurité

## Dépannage

### Problèmes Courants

1. **Utilisateur sans école assignée**
   - Vérifier le profil utilisateur
   - Assigner une école via l'admin Django

2. **Permissions insuffisantes**
   - Vérifier les permissions du profil
   - Contrôler les rôles et droits

3. **Sélection d'école non fonctionnelle**
   - Vérifier les middlewares dans settings.py
   - Contrôler les sessions utilisateur

### Logs Utiles
- `logs/security.log` : Événements de sécurité
- Console Django : Erreurs de middleware
- Base de données : Journal des activités

## Évolutions Futures

### Fonctionnalités Prévues
- Synchronisation inter-écoles
- Rapports consolidés multi-écoles
- Marketplace de templates
- API REST pour intégrations externes

### Optimisations
- Cache par école
- Optimisation des requêtes
- Compression des assets par école
