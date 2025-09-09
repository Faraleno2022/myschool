# 🚀 GUIDE DE DÉPLOIEMENT PRODUCTION - ÉCOLE MODERNE

**Version:** 1.0  
**Date:** Septembre 2025  
**Système:** Multi-tenant Django École Moderne

---

## 📋 PRÉ-REQUIS

### **Serveur de Production**
- **OS:** Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM:** Minimum 4GB (8GB recommandé)
- **CPU:** 2 cores minimum (4 cores recommandé)
- **Stockage:** 50GB minimum (SSD recommandé)
- **Python:** 3.9+
- **Base de données:** PostgreSQL 13+

### **Domaine et SSL**
- Nom de domaine configuré
- Certificat SSL (Let's Encrypt recommandé)
- DNS pointant vers le serveur

---

## 🔧 ÉTAPES DE DÉPLOIEMENT

### **1. Préparation du Serveur**

```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation des dépendances
sudo apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib
sudo apt install -y git curl wget unzip

# Installation de Node.js (pour les assets)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### **2. Configuration PostgreSQL**

```bash
# Connexion à PostgreSQL
sudo -u postgres psql

# Création de la base de données
CREATE DATABASE ecole_moderne_prod;
CREATE USER ecole_admin WITH PASSWORD 'MOT_DE_PASSE_SECURISE';
ALTER ROLE ecole_admin SET client_encoding TO 'utf8';
ALTER ROLE ecole_admin SET default_transaction_isolation TO 'read committed';
ALTER ROLE ecole_admin SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE ecole_moderne_prod TO ecole_admin;
\q
```

### **3. Déploiement de l'Application**

```bash
# Création du répertoire de déploiement
sudo mkdir -p /var/www/ecole_moderne
sudo chown $USER:$USER /var/www/ecole_moderne
cd /var/www/ecole_moderne

# Clonage du code (ou upload via FTP/SCP)
git clone https://github.com/votre-repo/ecole_moderne.git .

# Création de l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installation des dépendances
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### **4. Configuration de l'Environnement**

```bash
# Création du fichier .env de production
cat > .env << EOF
# Base de données
DATABASE_URL=postgresql://ecole_admin:MOT_DE_PASSE_SECURISE@localhost/ecole_moderne_prod

# Sécurité Django
SECRET_KEY=VOTRE_CLE_SECRETE_TRES_LONGUE_ET_ALEATOIRE
DEBUG=False
ALLOWED_HOSTS=votre-domaine.com,www.votre-domaine.com

# Email (optionnel)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=votre-email@gmail.com
EMAIL_HOST_PASSWORD=votre-mot-de-passe-app

# Sécurité
CSRF_TRUSTED_ORIGINS=https://votre-domaine.com,https://www.votre-domaine.com
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
EOF
```

### **5. Initialisation de la Base de Données**

```bash
# Activation de l'environnement
source venv/bin/activate

# Migrations
python manage.py makemigrations
python manage.py migrate

# Création du superutilisateur
python manage.py createsuperuser

# Collecte des fichiers statiques
python manage.py collectstatic --noinput

# Test du serveur
python manage.py runserver 0.0.0.0:8000
```

### **6. Configuration Gunicorn**

```bash
# Création du fichier de configuration Gunicorn
cat > gunicorn.conf.py << EOF
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
EOF

# Test Gunicorn
gunicorn --config gunicorn.conf.py ecole_moderne.wsgi:application
```

### **7. Configuration Nginx**

```bash
# Création de la configuration Nginx
sudo cat > /etc/nginx/sites-available/ecole_moderne << EOF
server {
    listen 80;
    server_name votre-domaine.com www.votre-domaine.com;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name votre-domaine.com www.votre-domaine.com;

    ssl_certificate /etc/letsencrypt/live/votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/votre-domaine.com/privkey.pem;

    # Sécurité SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    # Headers de sécurité
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/ecole_moderne;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        root /var/www/ecole_moderne;
        expires 1y;
        add_header Cache-Control "public";
    }

    location / {
        include proxy_params;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Limite de taille des uploads
    client_max_body_size 10M;
}
EOF

# Activation du site
sudo ln -s /etc/nginx/sites-available/ecole_moderne /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### **8. Configuration SSL avec Let's Encrypt**

```bash
# Installation Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtention du certificat
sudo certbot --nginx -d votre-domaine.com -d www.votre-domaine.com

# Test du renouvellement automatique
sudo certbot renew --dry-run
```

### **9. Configuration des Services Systemd**

```bash
# Service Gunicorn
sudo cat > /etc/systemd/system/ecole_moderne.service << EOF
[Unit]
Description=École Moderne Gunicorn daemon
Requires=ecole_moderne.socket
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
RuntimeDirectory=gunicorn
WorkingDirectory=/var/www/ecole_moderne
ExecStart=/var/www/ecole_moderne/venv/bin/gunicorn --config gunicorn.conf.py ecole_moderne.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Socket Gunicorn
sudo cat > /etc/systemd/system/ecole_moderne.socket << EOF
[Unit]
Description=École Moderne gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock
SocketUser=www-data

[Install]
WantedBy=sockets.target
EOF

# Activation des services
sudo systemctl daemon-reload
sudo systemctl enable ecole_moderne.socket
sudo systemctl start ecole_moderne.socket
sudo systemctl enable ecole_moderne.service
sudo systemctl start ecole_moderne.service
```

---

## 🔒 SÉCURITÉ PRODUCTION

### **1. Pare-feu**
```bash
# Configuration UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### **2. Sauvegarde Automatique**
```bash
# Script de sauvegarde
sudo cat > /usr/local/bin/backup_ecole_moderne.sh << EOF
#!/bin/bash
BACKUP_DIR="/var/backups/ecole_moderne"
DATE=\$(date +%Y%m%d_%H%M%S)

mkdir -p \$BACKUP_DIR

# Sauvegarde base de données
pg_dump -h localhost -U ecole_admin ecole_moderne_prod > \$BACKUP_DIR/db_\$DATE.sql

# Sauvegarde fichiers media
tar -czf \$BACKUP_DIR/media_\$DATE.tar.gz -C /var/www/ecole_moderne media/

# Nettoyage (garder 7 jours)
find \$BACKUP_DIR -name "*.sql" -mtime +7 -delete
find \$BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
EOF

sudo chmod +x /usr/local/bin/backup_ecole_moderne.sh

# Cron quotidien
echo "0 2 * * * root /usr/local/bin/backup_ecole_moderne.sh" | sudo tee -a /etc/crontab
```

### **3. Monitoring**
```bash
# Installation de monitoring basique
sudo apt install -y htop iotop nethogs

# Logs à surveiller
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
sudo journalctl -u ecole_moderne.service -f
```

---

## 📊 VÉRIFICATIONS POST-DÉPLOIEMENT

### **Checklist de Validation**
- [ ] Site accessible via HTTPS
- [ ] Certificat SSL valide
- [ ] Interface d'administration fonctionnelle
- [ ] Création de compte école testée
- [ ] Upload de fichiers fonctionnel
- [ ] Emails de notification envoyés
- [ ] Sauvegarde automatique configurée
- [ ] Monitoring en place

### **Tests de Performance**
```bash
# Test de charge basique
curl -o /dev/null -s -w "%{http_code} %{time_total}s\n" https://votre-domaine.com/

# Test des pages principales
curl -I https://votre-domaine.com/
curl -I https://votre-domaine.com/admin/
curl -I https://votre-domaine.com/ecole/inscription/
```

---

## 🚨 DÉPANNAGE

### **Problèmes Courants**

**1. Erreur 502 Bad Gateway**
```bash
sudo systemctl status ecole_moderne.service
sudo journalctl -u ecole_moderne.service -n 50
```

**2. Erreur de base de données**
```bash
sudo -u postgres psql ecole_moderne_prod
\dt  # Lister les tables
```

**3. Problème de permissions**
```bash
sudo chown -R www-data:www-data /var/www/ecole_moderne
sudo chmod -R 755 /var/www/ecole_moderne
```

**4. Certificat SSL expiré**
```bash
sudo certbot renew
sudo systemctl reload nginx
```

---

## 📞 SUPPORT

### **Logs Importants**
- Application: `sudo journalctl -u ecole_moderne.service`
- Nginx: `/var/log/nginx/error.log`
- PostgreSQL: `/var/log/postgresql/postgresql-13-main.log`

### **Commandes Utiles**
```bash
# Redémarrage complet
sudo systemctl restart ecole_moderne.service
sudo systemctl reload nginx

# Vérification statut
sudo systemctl status ecole_moderne.service
sudo systemctl status nginx
sudo systemctl status postgresql

# Mise à jour application
cd /var/www/ecole_moderne
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart ecole_moderne.service
```

---

**🎉 DÉPLOIEMENT TERMINÉ - SYSTÈME EN PRODUCTION !**
