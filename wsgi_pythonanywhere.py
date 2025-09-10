"""
WSGI config pour PythonAnywhere - École Moderne
Ce fichier doit être copié dans /var/www/www_myschoolgn_space_wsgi.py
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
