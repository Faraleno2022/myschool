# 🔒 Guide du Système de Permissions Granulaires pour Comptables

## 📋 Vue d'Ensemble

Le système de permissions granulaires permet de contrôler précisément les actions que peuvent effectuer les comptables dans l'application de gestion scolaire. Par défaut, les comptables sont **restreints** sur les actions sensibles pour garantir la sécurité.

## 🛡️ Permissions Disponibles

### ➕ **Permissions d'Ajout** (Par défaut : INTERDITES)
- **`peut_ajouter_paiements`** : Autoriser la création de nouveaux paiements
- **`peut_ajouter_depenses`** : Autoriser la création de nouvelles dépenses  
- **`peut_ajouter_enseignants`** : Autoriser l'ajout de nouveaux enseignants

### ✏️ **Permissions de Modification** (Par défaut : AUTORISÉES)
- **`peut_modifier_paiements`** : Modifier les paiements existants
- **`peut_modifier_depenses`** : Modifier les dépenses existantes

### 🗑️ **Permissions de Suppression** (Par défaut : INTERDITES)
- **`peut_supprimer_paiements`** : Supprimer des paiements
- **`peut_supprimer_depenses`** : Supprimer des dépenses

### 📊 **Permissions de Consultation** (Par défaut : AUTORISÉES)
- **`peut_consulter_rapports`** : Consulter les rapports
- **`peut_valider_paiements`** : Valider les paiements (selon configuration)
- **`peut_valider_depenses`** : Valider les dépenses (selon configuration)

## 🚀 Utilisation du Système

### 1. **Créer un Comptable avec Permissions**

```
URL : /utilisateurs/comptables/ajouter/
```

**Étapes :**
1. Remplir les informations utilisateur (nom, email, mot de passe)
2. Sélectionner l'école d'affectation
3. **Configurer les permissions granulaires** :
   - ❌ Par défaut : Ajouts et suppressions INTERDITS
   - ✅ Par défaut : Modifications et consultations AUTORISÉES
4. Cliquer sur "Créer"

### 2. **Gérer les Permissions Existantes**

```
URL : /utilisateurs/permissions/
```

**Interface de Gestion :**
- 📋 Liste de tous les comptables avec leurs permissions
- 🔄 Basculement en temps réel des permissions
- 📊 Export CSV des permissions
- 🔧 Actions en masse (tout autoriser/restreindre)

### 3. **Actions en Masse**

**Boutons disponibles :**
- **"Tout Autoriser"** : Accorde toutes les permissions
- **"Tout Restreindre"** : Retire toutes les permissions (sauf consultation)
- **"Configuration par Défaut"** : Applique la configuration sécurisée

## 🔧 Commandes de Gestion

### **Mise à Jour des Comptables Existants**

```bash
# Voir les changements sans les appliquer
python manage.py update_comptable_permissions --dry-run

# Appliquer la configuration par défaut (recommandé)
python manage.py update_comptable_permissions

# Tout restreindre (sécurité maximale)
python manage.py update_comptable_permissions --restrict-all

# Tout autoriser (pour cas spéciaux)
python manage.py update_comptable_permissions --allow-all
```

## 🎯 Scénarios d'Usage

### **Scénario 1 : Comptable Junior**
```
✅ Peut modifier paiements/dépenses
✅ Peut consulter rapports
❌ Ne peut pas ajouter paiements/dépenses
❌ Ne peut pas supprimer
❌ Ne peut pas ajouter enseignants
```

### **Scénario 2 : Comptable Senior**
```
✅ Peut modifier paiements/dépenses
✅ Peut consulter rapports
✅ Peut ajouter paiements/dépenses
✅ Peut valider paiements/dépenses
❌ Ne peut pas supprimer
❌ Ne peut pas ajouter enseignants
```

### **Scénario 3 : Comptable Chef**
```
✅ Toutes les permissions accordées
✅ Peut ajouter, modifier, supprimer
✅ Peut gérer enseignants
✅ Accès complet
```

## 🔒 Sécurité et Contrôles

### **Protection des Vues**

Les décorateurs suivants protègent automatiquement les vues :

```python
# Paiements
@can_add_payments        # ajouter_paiement()
@can_validate_payments   # valider_paiement()

# Dépenses  
@can_add_expenses        # ajouter_depense()
@can_modify_expenses     # modifier_depense()
@can_validate_expenses   # valider_depense()

# Enseignants
@can_add_teachers        # ajouter_enseignant()
```

### **Page d'Accès Refusé**

Quand un comptable tente d'accéder à une fonction interdite :
- 🚫 Page d'erreur personnalisée avec message explicite
- 📝 Log automatique de la tentative d'accès
- 🔄 Redirection vers page d'accueil après 30 secondes
- 📞 Informations de contact administrateur

## 📊 Monitoring et Logs

### **Logs de Sécurité**

Tous les événements sont enregistrés dans `logs/security.log` :
- Tentatives d'accès refusées
- Modifications de permissions
- Actions sensibles effectuées

### **Dashboard de Sécurité**

```
URL : /administration/security/
```

Surveillance en temps réel :
- 📈 Statistiques des tentatives d'accès
- 📋 Logs récents des permissions
- 🚨 Alertes de sécurité

## 🛠️ Configuration Technique

### **Modèle Profil Étendu**

Nouveaux champs ajoutés :
```python
peut_ajouter_paiements = BooleanField(default=False)
peut_ajouter_depenses = BooleanField(default=False)
peut_ajouter_enseignants = BooleanField(default=False)
peut_modifier_paiements = BooleanField(default=True)
peut_modifier_depenses = BooleanField(default=True)
peut_supprimer_paiements = BooleanField(default=False)
peut_supprimer_depenses = BooleanField(default=False)
peut_consulter_rapports = BooleanField(default=True)
```

### **Context Processor**

Permissions automatiquement disponibles dans tous les templates :
```django
{{ user_permissions.can_add_payments }}
{{ user_restrictions.cannot_add_payments }}
```

## 🚨 Bonnes Pratiques

### **Recommandations de Sécurité**

1. **🔒 Principe du Moindre Privilège** : Accordez uniquement les permissions nécessaires
2. **📋 Révision Régulière** : Vérifiez les permissions trimestriellement
3. **📝 Documentation** : Documentez les raisons des permissions accordées
4. **🔄 Rotation** : Changez les permissions selon l'évolution des rôles
5. **📊 Monitoring** : Surveillez les logs de sécurité quotidiennement

### **Configuration Recommandée par Rôle**

| Rôle | Ajouter | Modifier | Supprimer | Valider |
|------|---------|----------|-----------|---------|
| **Stagiaire** | ❌ | ✅ | ❌ | ❌ |
| **Comptable** | ❌ | ✅ | ❌ | ✅ |
| **Comptable Senior** | ✅ | ✅ | ❌ | ✅ |
| **Chef Comptable** | ✅ | ✅ | ✅ | ✅ |

## 📞 Support et Dépannage

### **Problèmes Courants**

**Q : Un comptable ne peut pas accéder à une fonction**
**R :** Vérifiez ses permissions dans `/utilisateurs/permissions/`

**Q : Comment réinitialiser toutes les permissions ?**
**R :** Utilisez `python manage.py update_comptable_permissions --restrict-all`

**Q : Les permissions ne s'appliquent pas**
**R :** Vérifiez que les migrations sont appliquées : `python manage.py migrate`

### **Contact Support**

- 📧 **Email** : admin@ecole.gn
- 📱 **Téléphone** : +224 XXX XX XX XX
- 🌐 **Documentation** : Consultez ce guide

---

## 🎉 Conclusion

Le système de permissions granulaires offre un contrôle total sur les accès des comptables, garantissant la sécurité tout en maintenant la flexibilité opérationnelle. Utilisez-le de manière responsable pour protéger vos données sensibles.

**🔐 Sécurité d'abord, flexibilité ensuite !**
