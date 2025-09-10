"""
Fichier de diagnostic temporaire pour PythonAnywhere
À utiliser TEMPORAIREMENT pour diagnostiquer les erreurs
"""
import os
from pathlib import Path
from .settings import *

# Configuration PyMySQL pour remplacer MySQLdb
import pymysql
pymysql.install_as_MySQLdb()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# TEMPORAIRE: Activer DEBUG pour voir les erreurs
DEBUG = True

# Hosts autorisés pour PythonAnywhere
ALLOWED_HOSTS = [
    'myschoolgn.pythonanywhere.com',
    'www.myschoolgn.space',
    'myschoolgn.space',
    'webapp-2750169.pythonanywhere.com',
    'localhost',
    '127.0.0.1',
    '*',  # TEMPORAIRE pour diagnostic
]

# Configuration de la base de données pour production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'myschoolgn$myschooldb',
        'USER': 'myschoolgn',
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': 'myschoolgn.mysql.pythonanywhere-services.com',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# Configuration des fichiers statiques pour production
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Configuration des fichiers média
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Logging pour diagnostic
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
    },
}
