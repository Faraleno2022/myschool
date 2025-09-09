"""
WSGI config pour PythonAnywhere
Ce fichier doit être placé dans le répertoire racine du projet sur PythonAnywhere
"""

import os
import sys

# Ajouter le chemin du projet
path = '/home/faraleno2022/myschool'
if path not in sys.path:
    sys.path.insert(0, path)

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings_production')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
