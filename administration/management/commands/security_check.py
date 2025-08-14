"""
Commande Django pour vérifier la sécurité de l'application
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
import os
import subprocess
import json
from datetime import datetime, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Effectue une vérification complète de la sécurité de l\'application'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Tente de corriger automatiquement les problèmes détectés',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Génère un rapport détaillé de sécurité',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== AUDIT DE SÉCURITÉ ==='))
        
        issues = []
        
        # 1. Vérifier les paramètres Django
        issues.extend(self.check_django_settings())
        
        # 2. Vérifier les utilisateurs
        issues.extend(self.check_users())
        
        # 3. Vérifier les permissions de fichiers
        issues.extend(self.check_file_permissions())
        
        # 4. Vérifier les dépendances
        issues.extend(self.check_dependencies())
        
        # 5. Vérifier les logs de sécurité
        issues.extend(self.check_security_logs())
        
        # Afficher le résumé
        self.display_summary(issues)
        
        # Corriger automatiquement si demandé
        if options['fix']:
            self.fix_issues(issues)
        
        # Générer un rapport si demandé
        if options['report']:
            self.generate_report(issues)
    
    def check_django_settings(self):
        """Vérifie les paramètres de sécurité Django"""
        issues = []
        
        # Vérifier DEBUG
        if settings.DEBUG:
            issues.append({
                'type': 'HIGH',
                'category': 'Configuration',
                'message': 'DEBUG est activé en production',
                'fix': 'Définir DEBUG=False en production'
            })
        
        # Vérifier SECRET_KEY
        if settings.SECRET_KEY == 'dev-unsafe-key':
            issues.append({
                'type': 'CRITICAL',
                'category': 'Configuration',
                'message': 'SECRET_KEY par défaut utilisée',
                'fix': 'Générer une nouvelle SECRET_KEY sécurisée'
            })
        
        # Vérifier ALLOWED_HOSTS
        if not settings.ALLOWED_HOSTS or '*' in settings.ALLOWED_HOSTS:
            issues.append({
                'type': 'HIGH',
                'category': 'Configuration',
                'message': 'ALLOWED_HOSTS mal configuré',
                'fix': 'Définir des hôtes spécifiques dans ALLOWED_HOSTS'
            })
        
        # Vérifier HTTPS
        if not settings.SECURE_SSL_REDIRECT and not settings.DEBUG:
            issues.append({
                'type': 'MEDIUM',
                'category': 'Configuration',
                'message': 'HTTPS non forcé en production',
                'fix': 'Activer SECURE_SSL_REDIRECT=True'
            })
        
        return issues
    
    def check_users(self):
        """Vérifie la sécurité des comptes utilisateurs"""
        issues = []
        
        # Vérifier les comptes admin avec mots de passe faibles
        weak_passwords = ['admin', 'password', '123456', 'admin123']
        
        for user in User.objects.filter(is_superuser=True):
            if user.check_password('admin') or user.check_password('password'):
                issues.append({
                    'type': 'CRITICAL',
                    'category': 'Utilisateurs',
                    'message': f'Compte admin {user.username} avec mot de passe faible',
                    'fix': 'Changer le mot de passe immédiatement'
                })
        
        # Vérifier les comptes inactifs
        inactive_threshold = datetime.now() - timedelta(days=90)
        inactive_users = User.objects.filter(
            last_login__lt=inactive_threshold,
            is_active=True
        )
        
        if inactive_users.exists():
            issues.append({
                'type': 'MEDIUM',
                'category': 'Utilisateurs',
                'message': f'{inactive_users.count()} comptes inactifs depuis 90+ jours',
                'fix': 'Désactiver ou supprimer les comptes inactifs'
            })
        
        return issues
    
    def check_file_permissions(self):
        """Vérifie les permissions des fichiers sensibles"""
        issues = []
        
        sensitive_files = [
            'db.sqlite3',
            'settings.py',
            'logs/security.log'
        ]
        
        for file_path in sensitive_files:
            full_path = os.path.join(settings.BASE_DIR, file_path)
            if os.path.exists(full_path):
                # Vérifier les permissions (Unix/Linux)
                if hasattr(os, 'stat'):
                    stat_info = os.stat(full_path)
                    permissions = oct(stat_info.st_mode)[-3:]
                    
                    if permissions == '777':
                        issues.append({
                            'type': 'HIGH',
                            'category': 'Permissions',
                            'message': f'Fichier {file_path} accessible en écriture par tous',
                            'fix': f'chmod 600 {file_path}'
                        })
        
        return issues
    
    def check_dependencies(self):
        """Vérifie les vulnérabilités dans les dépendances"""
        issues = []
        
        try:
            # Vérifier si safety est installé
            result = subprocess.run(['safety', 'check'], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                issues.append({
                    'type': 'MEDIUM',
                    'category': 'Dépendances',
                    'message': 'Vulnérabilités détectées dans les dépendances',
                    'fix': 'Mettre à jour les packages vulnérables'
                })
        except FileNotFoundError:
            issues.append({
                'type': 'LOW',
                'category': 'Outils',
                'message': 'Safety non installé pour vérifier les vulnérabilités',
                'fix': 'pip install safety'
            })
        
        return issues
    
    def check_security_logs(self):
        """Analyse les logs de sécurité"""
        issues = []
        
        log_file = os.path.join(settings.BASE_DIR, 'logs', 'security.log')
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                
                # Compter les tentatives d'attaque récentes
                recent_attacks = 0
                for line in lines[-1000:]:  # Dernières 1000 lignes
                    if any(keyword in line.lower() for keyword in 
                          ['injection', 'xss', 'attack', 'blocked']):
                        recent_attacks += 1
                
                if recent_attacks > 10:
                    issues.append({
                        'type': 'HIGH',
                        'category': 'Sécurité',
                        'message': f'{recent_attacks} tentatives d\'attaque récentes détectées',
                        'fix': 'Analyser les logs et renforcer la sécurité'
                    })
                
            except Exception as e:
                issues.append({
                    'type': 'LOW',
                    'category': 'Logs',
                    'message': f'Erreur lors de la lecture des logs: {e}',
                    'fix': 'Vérifier les permissions du fichier de log'
                })
        
        return issues
    
    def display_summary(self, issues):
        """Affiche le résumé des problèmes détectés"""
        critical = len([i for i in issues if i['type'] == 'CRITICAL'])
        high = len([i for i in issues if i['type'] == 'HIGH'])
        medium = len([i for i in issues if i['type'] == 'MEDIUM'])
        low = len([i for i in issues if i['type'] == 'LOW'])
        
        self.stdout.write('\n=== RÉSUMÉ DE L\'AUDIT ===')
        self.stdout.write(f'🔴 Critique: {critical}')
        self.stdout.write(f'🟠 Élevé: {high}')
        self.stdout.write(f'🟡 Moyen: {medium}')
        self.stdout.write(f'🟢 Faible: {low}')
        
        if issues:
            self.stdout.write('\n=== DÉTAILS DES PROBLÈMES ===')
            for issue in issues:
                color = {
                    'CRITICAL': self.style.ERROR,
                    'HIGH': self.style.WARNING,
                    'MEDIUM': self.style.NOTICE,
                    'LOW': self.style.SUCCESS
                }[issue['type']]
                
                self.stdout.write(
                    color(f"[{issue['type']}] {issue['category']}: {issue['message']}")
                )
                self.stdout.write(f"  💡 Solution: {issue['fix']}\n")
        else:
            self.stdout.write(self.style.SUCCESS('✅ Aucun problème de sécurité détecté!'))
    
    def fix_issues(self, issues):
        """Tente de corriger automatiquement certains problèmes"""
        self.stdout.write('\n=== CORRECTION AUTOMATIQUE ===')
        
        fixed = 0
        for issue in issues:
            if issue['category'] == 'Utilisateurs' and 'inactifs' in issue['message']:
                # Désactiver les comptes inactifs
                inactive_threshold = datetime.now() - timedelta(days=90)
                count = User.objects.filter(
                    last_login__lt=inactive_threshold,
                    is_active=True
                ).update(is_active=False)
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ {count} comptes inactifs désactivés')
                )
                fixed += 1
        
        self.stdout.write(f'\n{fixed} problèmes corrigés automatiquement.')
    
    def generate_report(self, issues):
        """Génère un rapport détaillé de sécurité"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_issues': len(issues),
            'issues_by_severity': {
                'critical': len([i for i in issues if i['type'] == 'CRITICAL']),
                'high': len([i for i in issues if i['type'] == 'HIGH']),
                'medium': len([i for i in issues if i['type'] == 'MEDIUM']),
                'low': len([i for i in issues if i['type'] == 'LOW'])
            },
            'issues': issues
        }
        
        report_file = os.path.join(settings.BASE_DIR, 'security_report.json')
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(
            self.style.SUCCESS(f'📄 Rapport généré: {report_file}')
        )
