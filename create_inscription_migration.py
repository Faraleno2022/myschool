#!/usr/bin/env python
"""
Script pour créer manuellement les migrations pour les nouveaux modèles d'inscription
"""
import os
import sys
import django
from django.conf import settings

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.db import connection
from django.core.management import execute_from_command_line

def create_tables_manually():
    """Créer les tables manuellement si les migrations échouent"""
    with connection.cursor() as cursor:
        # Table ClasseInscription
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inscription_ecoles_classeinscription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demande_inscription_id INTEGER NOT NULL,
                nom VARCHAR(100) NOT NULL,
                niveau VARCHAR(20) NOT NULL,
                code_matricule VARCHAR(12),
                capacite_max INTEGER NOT NULL DEFAULT 30,
                frais_inscription DECIMAL(10,0) NOT NULL DEFAULT 0,
                tranche_1 DECIMAL(10,0) NOT NULL DEFAULT 0,
                tranche_2 DECIMAL(10,0) NOT NULL DEFAULT 0,
                tranche_3 DECIMAL(10,0) NOT NULL DEFAULT 0,
                FOREIGN KEY (demande_inscription_id) REFERENCES inscription_ecoles_demandeinscriptionecole (id) ON DELETE CASCADE,
                UNIQUE (demande_inscription_id, nom)
            )
        """)
        
        # Table EcheancierInscription
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inscription_ecoles_echeancierinscription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demande_inscription_id INTEGER NOT NULL UNIQUE,
                annee_scolaire VARCHAR(9) NOT NULL,
                date_echeance_inscription DATE NOT NULL,
                date_echeance_tranche_1 DATE NOT NULL,
                date_echeance_tranche_2 DATE NOT NULL,
                date_echeance_tranche_3 DATE NOT NULL,
                autoriser_paiement_partiel BOOLEAN NOT NULL DEFAULT 1,
                penalite_retard DECIMAL(5,2) NOT NULL DEFAULT 0.00,
                FOREIGN KEY (demande_inscription_id) REFERENCES inscription_ecoles_demandeinscriptionecole (id) ON DELETE CASCADE
            )
        """)
        
        print("✅ Tables créées avec succès!")

def main():
    print("🚀 Création des migrations pour inscription_ecoles...")
    
    try:
        # Essayer d'abord la méthode normale
        print("Tentative de création des migrations...")
        execute_from_command_line(['manage.py', 'makemigrations', 'inscription_ecoles'])
        print("✅ Migrations créées avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur lors de la création des migrations: {e}")
        print("🔧 Création manuelle des tables...")
        create_tables_manually()
        
        # Créer un fichier de migration factice
        migration_content = '''# Generated manually
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal

class Migration(migrations.Migration):

    dependencies = [
        ('inscription_ecoles', '0002_demandeinscriptionecole_code_acces'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClasseInscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='Nom de la classe')),
                ('niveau', models.CharField(choices=[('GARDERIE', 'Garderie'), ('MATERNELLE', 'Maternelle'), ('PRIMAIRE_1', 'Primaire 1ère'), ('PRIMAIRE_2', 'Primaire 2ème'), ('PRIMAIRE_3', 'Primaire 3ème'), ('PRIMAIRE_4', 'Primaire 4ème'), ('PRIMAIRE_5', 'Primaire 5ème'), ('PRIMAIRE_6', 'Primaire 6ème'), ('COLLEGE_7', 'Collège 7ème'), ('COLLEGE_8', 'Collège 8ème'), ('COLLEGE_9', 'Collège 9ème'), ('COLLEGE_10', 'Collège 10ème'), ('LYCEE_11', 'Lycée 11ème'), ('LYCEE_12', 'Lycée 12ème'), ('TERMINALE', 'Terminale')], max_length=20, verbose_name='Niveau')),
                ('code_matricule', models.CharField(blank=True, help_text='Préfixe utilisé pour les matricules (ex: PN3, CN7, L11SL).', max_length=12, null=True, verbose_name='Code matricule')),
                ('capacite_max', models.PositiveIntegerField(default=30, verbose_name='Capacité maximale')),
                ('frais_inscription', models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, verbose_name="Frais d'inscription (GNF)")),
                ('tranche_1', models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, verbose_name='1ère tranche (GNF)')),
                ('tranche_2', models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, verbose_name='2ème tranche (GNF)')),
                ('tranche_3', models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, verbose_name='3ème tranche (GNF)')),
                ('demande_inscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classes_prevues', to='inscription_ecoles.demandeinscriptionecole')),
            ],
            options={
                'verbose_name': "Classe d'inscription",
                'verbose_name_plural': "Classes d'inscription",
            },
        ),
        migrations.CreateModel(
            name='EcheancierInscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('annee_scolaire', models.CharField(help_text='Format: 2024-2025', max_length=9, verbose_name='Année scolaire')),
                ('date_echeance_inscription', models.DateField(help_text="Date limite pour les frais d'inscription", verbose_name='Échéance inscription')),
                ('date_echeance_tranche_1', models.DateField(help_text='Date limite pour la 1ère tranche', verbose_name='Échéance 1ère tranche')),
                ('date_echeance_tranche_2', models.DateField(help_text='Date limite pour la 2ème tranche', verbose_name='Échéance 2ème tranche')),
                ('date_echeance_tranche_3', models.DateField(help_text='Date limite pour la 3ème tranche', verbose_name='Échéance 3ème tranche')),
                ('autoriser_paiement_partiel', models.BooleanField(default=True, verbose_name='Autoriser les paiements partiels')),
                ('penalite_retard', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Pourcentage de pénalité appliqué en cas de retard', max_digits=5, verbose_name='Pénalité de retard (%)')),
                ('demande_inscription', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='echeancier_prevu', to='inscription_ecoles.demandeinscriptionecole')),
            ],
            options={
                'verbose_name': "Échéancier d'inscription",
                'verbose_name_plural': "Échéanciers d'inscription",
            },
        ),
        migrations.AlterUniqueTogether(
            name='classeinscription',
            unique_together={('demande_inscription', 'nom')},
        ),
    ]
'''
        
        # Créer le répertoire migrations s'il n'existe pas
        migrations_dir = 'inscription_ecoles/migrations'
        os.makedirs(migrations_dir, exist_ok=True)
        
        # Écrire le fichier de migration
        with open(f'{migrations_dir}/0003_classeinscription_echeancierinscription.py', 'w', encoding='utf-8') as f:
            f.write(migration_content)
        
        print("✅ Fichier de migration créé manuellement!")

if __name__ == '__main__':
    main()
