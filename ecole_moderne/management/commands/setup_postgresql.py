"""
Commande de gestion pour configurer PostgreSQL et effectuer les migrations.
Usage: python manage.py setup_postgresql
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.conf import settings
import os
import sys


class Command(BaseCommand):
    help = 'Configure PostgreSQL database and run migrations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-db',
            action='store_true',
            help='Attempt to create the database if it does not exist',
        )
        parser.add_argument(
            '--migrate',
            action='store_true',
            help='Run migrations after database setup',
        )
        parser.add_argument(
            '--load-data',
            action='store_true',
            help='Load initial data after migrations',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== Configuration PostgreSQL pour École Moderne ===')
        )

        # Vérifier la configuration
        if not self._check_postgresql_config():
            return

        # Créer la base de données si demandé
        if options['create_db']:
            self._create_database()

        # Tester la connexion
        if not self._test_connection():
            return

        # Effectuer les migrations si demandé
        if options['migrate']:
            self._run_migrations()

        # Charger les données initiales si demandé
        if options['load_data']:
            self._load_initial_data()

        self.stdout.write(
            self.style.SUCCESS('✓ Configuration PostgreSQL terminée avec succès!')
        )

    def _check_postgresql_config(self):
        """Vérifier que PostgreSQL est configuré dans les settings"""
        db_engine = getattr(settings, 'DATABASE_ENGINE', 'sqlite3')
        
        if db_engine != 'postgresql':
            self.stdout.write(
                self.style.ERROR(
                    '✗ PostgreSQL n\'est pas configuré. '
                    'Définissez DATABASE_ENGINE=postgresql dans votre fichier .env'
                )
            )
            return False

        db_config = settings.DATABASES['default']
        required_fields = ['NAME', 'USER', 'HOST', 'PORT']
        
        for field in required_fields:
            if not db_config.get(field):
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Configuration manquante: DATABASE_{field} '
                        f'doit être défini dans votre fichier .env'
                    )
                )
                return False

        self.stdout.write(
            self.style.SUCCESS('✓ Configuration PostgreSQL détectée')
        )
        return True

    def _create_database(self):
        """Tenter de créer la base de données"""
        self.stdout.write('Tentative de création de la base de données...')
        
        try:
            import psycopg2
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            
            db_config = settings.DATABASES['default']
            
            # Connexion au serveur PostgreSQL (base postgres par défaut)
            conn = psycopg2.connect(
                host=db_config['HOST'],
                port=db_config['PORT'],
                user=db_config['USER'],
                password=db_config['PASSWORD'],
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            cursor = conn.cursor()
            
            # Vérifier si la base existe
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                [db_config['NAME']]
            )
            
            if cursor.fetchone():
                self.stdout.write(
                    self.style.WARNING(f'Base de données "{db_config["NAME"]}" existe déjà')
                )
            else:
                # Créer la base de données
                cursor.execute(f'CREATE DATABASE "{db_config["NAME"]}"')
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Base de données "{db_config["NAME"]}" créée')
                )
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Erreur lors de la création de la base: {e}')
            )

    def _test_connection(self):
        """Tester la connexion à la base de données"""
        self.stdout.write('Test de connexion à PostgreSQL...')
        
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT version()')
                version = cursor.fetchone()[0]
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Connexion réussie: {version}')
                )
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Erreur de connexion: {e}')
            )
            self.stdout.write(
                self.style.WARNING(
                    'Vérifiez que PostgreSQL est démarré et que les '
                    'paramètres de connexion sont corrects dans votre fichier .env'
                )
            )
            return False

    def _run_migrations(self):
        """Effectuer les migrations Django"""
        self.stdout.write('Exécution des migrations...')
        
        try:
            call_command('makemigrations', verbosity=1)
            call_command('migrate', verbosity=1)
            self.stdout.write(
                self.style.SUCCESS('✓ Migrations terminées')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Erreur lors des migrations: {e}')
            )

    def _load_initial_data(self):
        """Charger les données initiales"""
        self.stdout.write('Chargement des données initiales...')
        
        try:
            # Créer un superutilisateur si aucun n'existe
            from django.contrib.auth.models import User
            if not User.objects.filter(is_superuser=True).exists():
                self.stdout.write('Création d\'un superutilisateur...')
                call_command('createsuperuser', interactive=True)
            
            self.stdout.write(
                self.style.SUCCESS('✓ Données initiales chargées')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Erreur lors du chargement des données: {e}')
            )
