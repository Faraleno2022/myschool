import os
import sys
sys.path.append('/home/myschoolgn/monécole')
from ecole_moderne.settings import *

# Configuration pour la production
DEBUG = False

ALLOWED_HOSTS = ['myschoolgn.pythonanywhere.com', 'www.myschoolgn.space', 'localhost', '127.0.0.1']

# Configuration MySQL pour PythonAnywhere
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'myschoolgn$myschooldb',
        'USER': 'myschoolgn',
        'PASSWORD': 'Faraleno1994@',
        'HOST': 'myschoolgn.mysql.pythonanywhere-services.com',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Configuration des fichiers statiques
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Sécurité
SECURE_SSL_REDIRECT = False  # PythonAnywhere gère HTTPS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Configuration PyMySQL
import pymysql
pymysql.install_as_MySQLdb()
