# 🛡️ Guide de Sécurité - Système de Gestion Scolaire

## 🔒 Protections Implémentées

### 1. **Middleware de Sécurité**
- **Protection contre l'injection SQL** : Détection et blocage automatique
- **Protection XSS** : Filtrage des scripts malveillants
- **Protection Path Traversal** : Prévention de l'accès aux fichiers système
- **Rate Limiting** : Limitation à 100 requêtes/minute par IP
- **Blocage d'IP automatique** : 24h pour les tentatives d'attaque
- **Détection User-Agent suspects** : Blocage des outils de hacking

### 2. **Sécurité des Sessions**
- **Expiration automatique** : 30 minutes d'inactivité
- **Détection de détournement** : Surveillance des changements d'IP
- **Nettoyage sécurisé** : Suppression complète lors de la déconnexion
- **Cookies sécurisés** : HttpOnly, Secure, SameSite=Strict

### 3. **Authentification Renforcée**
- **Protection force brute** : Blocage après 5 tentatives échouées
- **Mots de passe forts** : Minimum 12 caractères obligatoire
- **Audit des connexions** : Logging complet des tentatives
- **Validation stricte** : Limitation de longueur des champs

### 4. **Configuration Django Sécurisée**
```python
# Paramètres de sécurité activés
SECURE_SSL_REDIRECT = True  # Force HTTPS
SECURE_HSTS_SECONDS = 31536000  # HSTS 1 an
X_FRAME_OPTIONS = 'DENY'  # Anti-clickjacking
SECURE_CONTENT_TYPE_NOSNIFF = True  # Anti-MIME sniffing
SECURE_BROWSER_XSS_FILTER = True  # Filtre XSS navigateur
```

## 🚨 Système d'Alertes

### Logs de Sécurité
- **Fichier** : `logs/security.log`
- **Niveaux** : INFO, WARNING, ERROR, CRITICAL
- **Rotation** : Automatique avec archivage

### Types d'Événements Surveillés
- Tentatives d'injection SQL
- Attaques XSS
- Tentatives de force brute
- User-Agents suspects
- Accès non autorisés
- Changements de permissions

## 🔧 Commandes de Sécurité

### Audit Complet
```bash
python manage.py security_check
```

### Audit avec Corrections Automatiques
```bash
python manage.py security_check --fix
```

### Génération de Rapport
```bash
python manage.py security_check --report
```

## 📊 Tableau de Bord Sécurité

Accessible via `/administration/security/` pour les administrateurs :
- Statistiques en temps réel
- Logs de sécurité récents
- Actions de sécurité rapides
- Statut des protections

## 🛠️ Décorateurs de Sécurité

### Utilisation dans les Vues
```python
from ecole_moderne.security_decorators import secure_view, rate_limit, admin_required

@secure_view(admin_only=True, rate_limit_requests=10)
def ma_vue_securisee(request):
    # Code de la vue
    pass

@rate_limit(max_requests=5, window=60)
def vue_limitee(request):
    # Maximum 5 requêtes par minute
    pass
```

## 🔐 Bonnes Pratiques

### Pour les Administrateurs
1. **Mots de passe** : Minimum 12 caractères, complexes
2. **Sessions** : Déconnexion après utilisation
3. **Surveillance** : Vérification régulière des logs
4. **Mises à jour** : Application des correctifs de sécurité

### Pour les Développeurs
1. **Validation** : Toujours valider les entrées utilisateur
2. **Échappement** : Utiliser les templates Django sécurisés
3. **Permissions** : Vérifier les autorisations sur chaque vue
4. **Logs** : Enregistrer les actions sensibles

## 🚫 Protections Actives

### Contre les Attaques Communes
- **SQL Injection** : Filtrage par regex + ORM Django
- **XSS** : Échappement automatique + CSP headers
- **CSRF** : Tokens Django + vérification Referer
- **Clickjacking** : X-Frame-Options: DENY
- **Session Fixation** : Régénération automatique

### Limitations de Sécurité
- **Upload** : 5MB maximum par fichier
- **Champs** : 150 caractères max pour username
- **Requêtes** : 100 par minute par IP
- **Connexions** : 5 tentatives avant blocage

## 📈 Monitoring

### Métriques Surveillées
- Nombre d'IP bloquées
- Tentatives de connexion échouées
- Sessions actives
- Temps de réponse des requêtes
- Utilisation des ressources

### Alertes Automatiques
- Blocage d'IP après attaque
- Détection de patterns suspects
- Échecs de connexion répétés
- Accès non autorisés

## 🔄 Maintenance de Sécurité

### Tâches Quotidiennes
- Vérification des logs de sécurité
- Analyse des tentatives d'attaque
- Surveillance des performances

### Tâches Hebdomadaires
- Audit complet de sécurité
- Mise à jour des règles de blocage
- Vérification des comptes utilisateurs

### Tâches Mensuelles
- Révision des permissions
- Test des procédures de sécurité
- Mise à jour des dépendances

## 🆘 Procédures d'Urgence

### En Cas d'Attaque Détectée
1. **Identifier** la source de l'attaque
2. **Bloquer** l'IP suspecte immédiatement
3. **Analyser** les logs pour comprendre l'attaque
4. **Renforcer** les protections si nécessaire
5. **Documenter** l'incident

### Verrouillage d'Urgence
```python
# Activer le mode maintenance
MAINTENANCE_MODE = True
# Bloquer tous les accès sauf admin
EMERGENCY_LOCKDOWN = True
```

## 📞 Contacts de Sécurité

En cas d'incident de sécurité critique :
- **Administrateur Système** : admin@ecole.gn
- **Équipe Technique** : tech@ecole.gn
- **Urgences** : +224 XXX XX XX XX

---

**⚠️ IMPORTANT** : Ce système de sécurité est conçu pour protéger contre les attaques communes. Une surveillance continue et des mises à jour régulières sont essentielles pour maintenir un niveau de sécurité optimal.
