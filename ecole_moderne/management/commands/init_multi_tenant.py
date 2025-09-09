"""
Commande de gestion pour initialiser le système multi-tenant
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from eleves.models import Ecole
from utilisateurs.models import Profil
from inscription_ecoles.models import ConfigurationEcole, TemplateDocument


class Command(BaseCommand):
    help = 'Initialise le système multi-tenant avec des données de base'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-demo-schools',
            action='store_true',
            help='Créer des écoles de démonstration',
        )
        parser.add_argument(
            '--create-templates',
            action='store_true',
            help='Créer les templates de documents par défaut',
        )
        parser.add_argument(
            '--assign-existing-users',
            action='store_true',
            help='Assigner les utilisateurs existants à une école par défaut',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Initialisation du système multi-tenant...')
        )

        with transaction.atomic():
            # Créer une école par défaut si aucune n'existe
            self.create_default_school()
            
            if options['create_demo_schools']:
                self.create_demo_schools()
            
            if options['create_templates']:
                self.create_default_templates()
            
            if options['assign_existing_users']:
                self.assign_existing_users()

        self.stdout.write(
            self.style.SUCCESS('✅ Initialisation terminée avec succès!')
        )

    def create_default_school(self):
        """Créer une école par défaut"""
        if not Ecole.objects.exists():
            ecole = Ecole.objects.create(
                nom="École Moderne",
                nom_complet="École Moderne - Établissement Principal",
                slug="ecole-moderne",
                type_ecole="PRIVEE",
                adresse="Conakry, Guinée",
                ville="Conakry",
                prefecture="Conakry",
                telephone="+224622613559",
                email="contact@ecole-moderne.gn",
                directeur="Direction Générale",
                statut="ACTIVE"
            )
            
            # Créer la configuration par défaut
            ConfigurationEcole.objects.create(ecole=ecole)
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ École par défaut créée: {ecole.nom}')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠️  Des écoles existent déjà')
            )

    def create_demo_schools(self):
        """Créer des écoles de démonstration"""
        demo_schools = [
            {
                'nom': 'Collège Sainte-Marie',
                'nom_complet': 'Collège Sainte-Marie de Conakry',
                'slug': 'college-sainte-marie',
                'type_ecole': 'CONFESSIONNELLE',
                'ville': 'Conakry',
                'prefecture': 'Conakry',
                'telephone': '+224621234567',
                'email': 'contact@sainte-marie.gn',
                'directeur': 'Sœur Marie-Claire',
            },
            {
                'nom': 'Lycée Technique de Kindia',
                'nom_complet': 'Lycée Technique et Professionnel de Kindia',
                'slug': 'lycee-technique-kindia',
                'type_ecole': 'PUBLIQUE',
                'ville': 'Kindia',
                'prefecture': 'Kindia',
                'telephone': '+224625678901',
                'email': 'contact@lycee-kindia.edu.gn',
                'directeur': 'M. Mamadou Diallo',
            },
            {
                'nom': 'École Internationale de Kankan',
                'nom_complet': 'École Internationale Bilingue de Kankan',
                'slug': 'ecole-internationale-kankan',
                'type_ecole': 'INTERNATIONALE',
                'ville': 'Kankan',
                'prefecture': 'Kankan',
                'telephone': '+224627890123',
                'email': 'info@international-kankan.org',
                'directeur': 'Dr. Fatou Camara',
            }
        ]

        for school_data in demo_schools:
            if not Ecole.objects.filter(slug=school_data['slug']).exists():
                school_data['adresse'] = f"{school_data['ville']}, {school_data['prefecture']}, Guinée"
                school_data['statut'] = 'ACTIVE'
                
                ecole = Ecole.objects.create(**school_data)
                ConfigurationEcole.objects.create(ecole=ecole)
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ École de démo créée: {ecole.nom}')
                )

    def create_default_templates(self):
        """Créer les templates de documents par défaut"""
        templates = [
            {
                'nom': 'Fiche d\'inscription standard',
                'type_document': 'FICHE_INSCRIPTION',
                'contenu_html': '''
                <div class="fiche-inscription">
                    <h1>FICHE D'INSCRIPTION</h1>
                    <div class="ecole-info">
                        <h2>{{ecole_nom}}</h2>
                        <p>{{ecole_adresse}}</p>
                        <p>Tél: {{ecole_telephone}} | Email: {{ecole_email}}</p>
                    </div>
                    <div class="eleve-info">
                        <h3>Informations de l'élève</h3>
                        <p><strong>Nom:</strong> {{eleve_nom}}</p>
                        <p><strong>Prénom:</strong> {{eleve_prenom}}</p>
                        <p><strong>Classe:</strong> {{classe}}</p>
                        <p><strong>Date de naissance:</strong> {{date_naissance}}</p>
                    </div>
                </div>
                ''',
                'styles_css': '''
                .fiche-inscription { font-family: Arial, sans-serif; }
                h1 { text-align: center; color: #1976d2; }
                .ecole-info { border-bottom: 2px solid #1976d2; padding-bottom: 10px; }
                .eleve-info { margin-top: 20px; }
                '''
            },
            {
                'nom': 'Reçu de paiement standard',
                'type_document': 'RECU_PAIEMENT',
                'contenu_html': '''
                <div class="recu-paiement">
                    <h1>REÇU DE PAIEMENT</h1>
                    <div class="numero-recu">N° {{numero_recu}}</div>
                    <div class="ecole-info">
                        <h2>{{ecole_nom}}</h2>
                        <p>{{ecole_adresse}}</p>
                    </div>
                    <div class="paiement-info">
                        <p><strong>Élève:</strong> {{eleve_nom}}</p>
                        <p><strong>Montant:</strong> {{montant}}</p>
                        <p><strong>Date:</strong> {{date}}</p>
                        <p><strong>Mode de paiement:</strong> {{mode_paiement}}</p>
                    </div>
                    <div class="signature">
                        <p>Signature et cachet de l'établissement</p>
                    </div>
                </div>
                ''',
                'styles_css': '''
                .recu-paiement { font-family: Arial, sans-serif; }
                h1 { text-align: center; color: #28a745; }
                .numero-recu { text-align: right; font-weight: bold; }
                .signature { margin-top: 50px; text-align: right; }
                '''
            }
        ]

        for template_data in templates:
            if not TemplateDocument.objects.filter(
                nom=template_data['nom'],
                ecole__isnull=True
            ).exists():
                template_data['est_par_defaut'] = True
                template_data['est_actif'] = True
                
                TemplateDocument.objects.create(**template_data)
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Template créé: {template_data["nom"]}')
                )

    def assign_existing_users(self):
        """Assigner les utilisateurs existants à une école par défaut"""
        ecole_defaut = Ecole.objects.first()
        if not ecole_defaut:
            self.stdout.write(
                self.style.ERROR('❌ Aucune école disponible pour l\'assignation')
            )
            return

        users_sans_profil = User.objects.filter(profil__isnull=True)
        
        for user in users_sans_profil:
            # Déterminer le rôle selon les permissions Django
            if user.is_superuser:
                role = 'ADMIN'
            elif user.is_staff:
                role = 'DIRECTEUR'
            else:
                role = 'COMPTABLE'
            
            Profil.objects.create(
                user=user,
                role=role,
                telephone='+224600000000',  # Téléphone par défaut
                ecole=ecole_defaut,
                peut_valider_paiements=user.is_staff,
                peut_valider_depenses=user.is_staff,
                peut_generer_rapports=True,
                peut_gerer_utilisateurs=user.is_superuser,
                actif=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Profil créé pour: {user.username} ({role})')
            )

        # Mettre à jour les profils existants sans école
        profils_sans_ecole = Profil.objects.filter(ecole__isnull=True)
        for profil in profils_sans_ecole:
            profil.ecole = ecole_defaut
            profil.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ École assignée à: {profil.user.username}')
            )
