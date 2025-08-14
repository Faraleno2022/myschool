from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.utils import timezone as django_timezone
from decimal import Decimal
import json
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from .models import Rapport, TypeRapport, ExportProgramme
from .utils import collecter_donnees_periode, generer_pdf_periode, _draw_header_and_watermark
from eleves.models import Eleve, Ecole
from paiements.models import Paiement, PaiementRemise
from depenses.models import Depense
from salaires.models import Enseignant, EtatSalaire
from utilisateurs.utils import user_is_admin, user_school

# Décorateur d'accès admin uniquement
admin_required = user_passes_test(user_is_admin)

@login_required
@admin_required
def tableau_bord(request):
    """Vue principale du module Rapports"""
    context = {
        'rapports_recents': Rapport.objects.filter(
            genere_par=request.user
        ).order_by('-date_generation')[:10],
        'types_rapports': TypeRapport.objects.filter(actif=True),
        'exports_programmes': ExportProgramme.objects.filter(
            cree_par=request.user,
            statut='ACTIF'
        )[:5],
        'today': date.today()
    }
    return render(request, 'rapports/tableau_bord.html', context)

@login_required
@admin_required
def generer_rapport_journalier(request):
    """Génère un rapport journalier automatique"""
    date_rapport = date.today()
    if request.GET.get('date'):
        date_rapport = datetime.strptime(request.GET.get('date'), '%Y-%m-%d').date()
    
    # Collecte des données journalières
    donnees = collecter_donnees_journalieres(date_rapport, user=request.user)
    
    # Génération du PDF
    pdf_buffer = generer_pdf_journalier(donnees, date_rapport)
    
    # Sauvegarde du rapport
    rapport = Rapport.objects.create(
        type_rapport=get_or_create_type_rapport('JOURNALIER'),
        titre=f"Rapport Journalier - {date_rapport.strftime('%d/%m/%Y')}",
        periode_debut=date_rapport,
        periode_fin=date_rapport,
        format_rapport='PDF',
        statut='TERMINE',
        genere_par=request.user,
        parametres=json.dumps(donnees, default=str)
    )
    
    # Sauvegarde du fichier PDF
    rapport.fichier.save(
        f'rapport_journalier_{date_rapport.strftime("%Y%m%d")}.pdf',
        pdf_buffer
    )
    
    return HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')

@login_required
@admin_required
def generer_rapport_hebdomadaire(request):
    """Génère un rapport hebdomadaire"""
    # Calcul de la semaine (lundi à dimanche)
    aujourd_hui = date.today()
    debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    fin_semaine = debut_semaine + timedelta(days=6)
    
    if request.GET.get('debut'):
        debut_semaine = datetime.strptime(request.GET.get('debut'), '%Y-%m-%d').date()
        fin_semaine = debut_semaine + timedelta(days=6)
    
    # Convertir les dates en datetime timezone-aware pour éviter les warnings
    debut_dt = django_timezone.make_aware(datetime.combine(debut_semaine, datetime.min.time()))
    fin_dt = django_timezone.make_aware(datetime.combine(fin_semaine, datetime.max.time()))
    
    donnees = collecter_donnees_periode(debut_dt, fin_dt, 'HEBDOMADAIRE', user=request.user)
    pdf_buffer = generer_pdf_periode(donnees, debut_semaine, fin_semaine, 'HEBDOMADAIRE')
    
    # Sauvegarde
    rapport = Rapport.objects.create(
        type_rapport=get_or_create_type_rapport('HEBDOMADAIRE'),
        titre=f"Rapport Hebdomadaire - {debut_semaine.strftime('%d/%m')} au {fin_semaine.strftime('%d/%m/%Y')}",
        periode_debut=datetime.combine(debut_semaine, datetime.min.time()),
        periode_fin=datetime.combine(fin_semaine, datetime.max.time()),
        format_rapport='PDF',
        statut='TERMINE',
        genere_par=request.user,
        parametres=json.dumps(donnees, default=str)
    )
    
    rapport.fichier.save(
        f'rapport_hebdomadaire_{debut_semaine.strftime("%Y%m%d")}.pdf',
        pdf_buffer
    )
    
    return HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')

@login_required
@admin_required
def generer_rapport_mensuel(request):
    """Génère un rapport mensuel"""
    aujourd_hui = date.today()
    debut_mois = aujourd_hui.replace(day=1)
    fin_mois = (debut_mois + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    if request.GET.get('mois') and request.GET.get('annee'):
        mois = int(request.GET.get('mois'))
        annee = int(request.GET.get('annee'))
        debut_mois = date(annee, mois, 1)
        fin_mois = (debut_mois + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Convertir les dates en datetime timezone-aware pour éviter les warnings
    debut_dt = django_timezone.make_aware(datetime.combine(debut_mois, datetime.min.time()))
    fin_dt = django_timezone.make_aware(datetime.combine(fin_mois, datetime.max.time()))
    
    donnees = collecter_donnees_periode(debut_dt, fin_dt, 'MENSUEL', user=request.user)
    pdf_buffer = generer_pdf_periode(donnees, debut_mois, fin_mois, 'MENSUEL')
    
    # Sauvegarde
    rapport = Rapport.objects.create(
        type_rapport=get_or_create_type_rapport('MENSUEL'),
        titre=f"Rapport Mensuel - {debut_mois.strftime('%B %Y')}",
        periode_debut=datetime.combine(debut_mois, datetime.min.time()),
        periode_fin=datetime.combine(fin_mois, datetime.max.time()),
        format_rapport='PDF',
        statut='TERMINE',
        genere_par=request.user,
        parametres=json.dumps(donnees, default=str)
    )
    
    rapport.fichier.save(
        f'rapport_mensuel_{debut_mois.strftime("%Y%m")}.pdf',
        pdf_buffer
    )
    
    return HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')

@login_required
@admin_required
def generer_rapport_annuel(request):
    """Génère un rapport annuel"""
    aujourd_hui = date.today()
    debut_annee = date(aujourd_hui.year, 1, 1)
    fin_annee = date(aujourd_hui.year, 12, 31)
    
    if request.GET.get('annee'):
        annee = int(request.GET.get('annee'))
        debut_annee = date(annee, 1, 1)
        fin_annee = date(annee, 12, 31)
    
    # Convertir les dates en datetime timezone-aware pour éviter les warnings
    debut_dt = django_timezone.make_aware(datetime.combine(debut_annee, datetime.min.time()))
    fin_dt = django_timezone.make_aware(datetime.combine(fin_annee, datetime.max.time()))
    
    donnees = collecter_donnees_periode(debut_dt, fin_dt, 'ANNUEL', user=request.user)
    pdf_buffer = generer_pdf_periode(donnees, debut_annee, fin_annee, 'ANNUEL')
    
    # Sauvegarde
    rapport = Rapport.objects.create(
        type_rapport=get_or_create_type_rapport('ANNUEL'),
        titre=f"Rapport Annuel - {debut_annee.year}",
        periode_debut=datetime.combine(debut_annee, datetime.min.time()),
        periode_fin=datetime.combine(fin_annee, datetime.max.time()),
        format_rapport='PDF',
        statut='TERMINE',
        genere_par=request.user,
        parametres=json.dumps(donnees, default=str)
    )
    
    rapport.fichier.save(
        f'rapport_annuel_{debut_annee.year}.pdf',
        pdf_buffer
    )
    
    return HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')

@login_required
@admin_required
def liste_rapports(request):
    """Liste tous les rapports générés"""
    rapports = Rapport.objects.filter(
        genere_par=request.user
    ).order_by('-date_generation')
    
    context = {
        'rapports': rapports
    }
    return render(request, 'rapports/liste_rapports.html', context)

def get_or_create_type_rapport(nom):
    """Récupère ou crée un type de rapport"""
    type_rapport, created = TypeRapport.objects.get_or_create(
        nom=nom,
        defaults={
            'description': f'Rapport {nom.lower()}',
            'categorie': 'FINANCIER',
            'template_path': f'rapports/{nom.lower()}.html',
            'actif': True
        }
    )
    return type_rapport

def collecter_donnees_journalieres(date_rapport, user=None):
    """Collecte toutes les données importantes pour le rapport journalier"""
    donnees = {
        'date': date_rapport,
        'ecoles': {},
        # Dépenses non reliées à l'école: globales pour la journée
        'depenses_globales': {
            'nombre': 0,  # initialisé, sera remplacé par des entiers
            'montant_total': Decimal('0')
        }
    }

    # Restreindre le périmètre des écoles selon l'utilisateur
    ecoles_qs = Ecole.objects.all()
    if user is not None and not user_is_admin(user):
        ecole_user = user_school(user)
        ecoles_qs = ecoles_qs.filter(id=getattr(ecole_user, 'id', None)) if ecole_user else Ecole.objects.none()

    # Dépenses du jour (GLOBAL - pas de relation à Ecole)
    depenses_jour_global = Depense.objects.filter(
        date_facture=date_rapport,
        statut='VALIDEE'
    )
    donnees['depenses_globales']['nombre'] = depenses_jour_global.count()
    donnees['depenses_globales']['montant_total'] = depenses_jour_global.aggregate(
        total=Sum('montant_ttc')
    )['total'] or Decimal('0')

    # Pour chaque école
    for ecole in ecoles_qs:
        donnees_ecole = {
            'nom': ecole.nom,
            'nouveaux_eleves': Eleve.objects.filter(
                classe__ecole=ecole,
                date_inscription=date_rapport
            ).count(),
            'paiements': {
                'nombre': 0,
                'montant_total': Decimal('0'),
                'frais_inscription': Decimal('0'),
                'scolarite': Decimal('0')
            },
            # Dépenses affichées par école mises à 0 pour éviter toute confusion,
            # car le modèle Depense n'est pas lié à Ecole. Un total global sera affiché.
            'depenses': {
                'nombre': 0,
                'montant_total': Decimal('0')
            },
            'salaires': {
                'etats_valides': 0,
                'montant_total': Decimal('0')
            }
        }
        
        # Paiements du jour - utiliser une approche plus flexible
        paiements_jour = Paiement.objects.filter(
            eleve__classe__ecole=ecole,
            date_paiement=date_rapport
        ).exclude(statut='ANNULE')  # Exclure seulement les annulés
        
        # Si pas de paiements ce jour, essayer avec les paiements récents (30 derniers jours)
        if not paiements_jour.exists():
            date_limite = date_rapport - timedelta(days=30)
            paiements_jour = Paiement.objects.filter(
                eleve__classe__ecole=ecole,
                date_paiement__gte=date_limite,
                statut='VALIDE'
            )
        
        donnees_ecole['paiements']['nombre'] = paiements_jour.count()
        donnees_ecole['paiements']['montant_total'] = paiements_jour.aggregate(
            total=Sum('montant')
        )['total'] or Decimal('0')
        
        # Calculer les remises appliquées
        remises_appliquees = PaiementRemise.objects.filter(
            paiement__in=paiements_jour
        ).aggregate(
            total_remises=Sum('montant_remise')
        )['total_remises'] or Decimal('0')
        
        # Calculer le montant original (avant remises)
        montant_original = donnees_ecole['paiements']['montant_total'] + remises_appliquees
        
        # Ajouter les données des remises
        donnees_ecole['paiements']['montant_original'] = montant_original
        donnees_ecole['paiements']['total_remises'] = remises_appliquees
        donnees_ecole['paiements']['montant_net'] = donnees_ecole['paiements']['montant_total']
        
        # Séparation frais d'inscription et scolarité
        # LOGIQUE CORRIGÉE: sans dépendre des TypePaiement qui peuvent être absents
        
        # Calculer les frais d'inscription théoriques (30 000 GNF par nouvel élève)
        nb_nouveaux_eleves = donnees_ecole['nouveaux_eleves']
        frais_inscription_theoriques = nb_nouveaux_eleves * Decimal('30000')
        
        # Essayer de détecter les paiements d'inscription par type (si TypePaiement existe)
        frais_inscription_payes = Decimal('0')
        try:
            frais_inscription_payes = paiements_jour.filter(
                Q(type_paiement__nom__icontains='inscription') |
                Q(type_paiement__nom__icontains='Inscription') |
                Q(type_paiement__nom__icontains='INSCRIPTION')
            ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
        except Exception:
            # Si pas de TypePaiement ou erreur, on utilise la logique alternative
            pass
        
        # LOGIQUE ALTERNATIVE: si pas de types définis, analyser les montants
        if frais_inscription_payes == 0 and donnees_ecole['paiements']['montant_total'] > 0:
            # Heuristique: les paiements de 30k sont probablement des frais d'inscription
            paiements_30k = paiements_jour.filter(montant=30000).aggregate(
                total=Sum('montant')
            )['total'] or Decimal('0')
            
            if paiements_30k > 0:
                frais_inscription_payes = paiements_30k
            else:
                # Fallback: utiliser les frais théoriques si nouveaux élèves
                frais_inscription_payes = frais_inscription_theoriques
        
        # Calculer la scolarité (reste des paiements)
        scolarite_payee = donnees_ecole['paiements']['montant_total'] - frais_inscription_payes
        
        # Assigner les valeurs finales
        donnees_ecole['paiements']['frais_inscription'] = frais_inscription_payes
        donnees_ecole['paiements']['scolarite'] = max(scolarite_payee, Decimal('0'))  # Éviter négatif
        
        # Dépenses: pas de répartition par école (le modèle n'est pas rattaché à Ecole)
        # On laisse 0 au niveau de l'école et on affiche un total global dans le résumé

        # États de salaire validés
        # Convertir la date en timezone aware pour éviter les warnings
        debut_jour = django_timezone.make_aware(datetime.combine(date_rapport, datetime.min.time()))
        fin_jour = django_timezone.make_aware(datetime.combine(date_rapport, datetime.max.time()))
        
        etats_jour = EtatSalaire.objects.filter(
            enseignant__ecole=ecole,
            date_validation__range=[debut_jour, fin_jour],
            valide=True
        )
        
        donnees_ecole['salaires']['etats_valides'] = etats_jour.count()
        donnees_ecole['salaires']['montant_total'] = etats_jour.aggregate(
            total=Sum('salaire_net')
        )['total'] or Decimal('0')
        
        donnees['ecoles'][ecole.id] = donnees_ecole
    
    return donnees

def generer_pdf_journalier(donnees, date_rapport):
    """Génère le PDF du rapport journalier"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Titre
    titre_style = ParagraphStyle(
        'TitreRapport',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.darkblue,
        alignment=1  # Centré
    )
    
    story.append(Paragraph(f"RAPPORT JOURNALIER - {date_rapport.strftime('%d/%m/%Y')}", titre_style))
    story.append(Spacer(1, 20))
    
    # Pour chaque école
    for ecole_id, donnees_ecole in donnees['ecoles'].items():
        # Titre de l'école
        story.append(Paragraph(f"École: {donnees_ecole['nom']}", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        # Tableau des données
        data = [
            ['Indicateur', 'Valeur'],
            ['Nouveaux élèves inscrits', str(donnees_ecole['nouveaux_eleves'])],
            ['Nombre de paiements', str(donnees_ecole['paiements']['nombre'])],
            ['Montant original (avant remises)', f"{donnees_ecole['paiements']['montant_original']:,} GNF".replace(',', ' ')],
            ['Total des remises accordées', f"{donnees_ecole['paiements']['total_remises']:,} GNF".replace(',', ' ')],
            ['Montant net encaissé', f"{donnees_ecole['paiements']['montant_total']:,} GNF".replace(',', ' ')],
            ['Frais d\'inscription', f"{donnees_ecole['paiements']['frais_inscription']:,} GNF".replace(',', ' ')],
            ['Scolarité', f"{donnees_ecole['paiements']['scolarite']:,} GNF".replace(',', ' ')],
            ['Nombre de dépenses', str(donnees_ecole['depenses']['nombre'])],
            ['Montant total des dépenses', f"{donnees_ecole['depenses']['montant_total']:,} GNF".replace(',', ' ')],
            ['États de salaire validés', str(donnees_ecole['salaires']['etats_valides'])],
            ['Montant total des salaires', f"{donnees_ecole['salaires']['montant_total']:,} GNF".replace(',', ' ')],
        ]
        
        table = Table(data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Section Dépenses globales (non rattachées à une école)
    story.append(Paragraph("DÉPENSES GLOBALES (journée)", styles['Heading2']))
    story.append(Spacer(1, 8))
    dep_global = donnees.get('depenses_globales', {'nombre': 0, 'montant_total': Decimal('0')})
    depenses_data = [
        ['Nombre de dépenses', str(dep_global.get('nombre', 0))],
        ['Montant total des dépenses', f"{dep_global.get('montant_total', Decimal('0')):,} GNF".replace(',', ' ')]
    ]
    dep_table = Table(depenses_data, colWidths=[3*inch, 2*inch])
    dep_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(dep_table)
    story.append(Spacer(1, 16))

    # Résumé global
    total_paiements = sum(d['paiements']['montant_total'] for d in donnees['ecoles'].values())
    total_depenses = donnees['depenses_globales']['montant_total']
    total_paiements_original = sum(d['paiements']['montant_original'] for d in donnees['ecoles'].values())
    total_remises = sum(d['paiements']['total_remises'] for d in donnees['ecoles'].values())
    total_salaires = sum(d['salaires']['montant_total'] for d in donnees['ecoles'].values())
    
    # Résumé global
    resume_data = [
        ['Indicateur', 'Montant'],
        ['Montant original des paiements', f"{total_paiements_original:,} GNF".replace(',', ' ')],
        ['Total des remises accordées', f"{total_remises:,} GNF".replace(',', ' ')],
        ['Montant net des paiements', f"{total_paiements:,} GNF".replace(',', ' ')],
        ['Total des dépenses', f"{total_depenses:,} GNF".replace(',', ' ')],
        ['Total des salaires', f"{total_salaires:,} GNF".replace(',', ' ')],
        ['Solde net', f"{total_paiements - total_depenses - total_salaires:,} GNF".replace(',', ' ')],
    ]
    
    resume_table = Table(resume_data, colWidths=[3*inch, 2*inch])
    resume_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(resume_table)
    
    # Ajout entête + filigrane sur toutes les pages
    doc.build(story, onFirstPage=_draw_header_and_watermark, onLaterPages=_draw_header_and_watermark)
    buffer.seek(0)
    return buffer


@login_required
@admin_required
def rapport_remises_detaille(request):
    """Rapport détaillé des remises appliquées"""
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    # Dates par défaut (mois en cours)
    if not date_debut:
        date_debut = date.today().replace(day=1)
    else:
        date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
    
    if not date_fin:
        date_fin = date.today()
    else:
        date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
    
    # Récupérer toutes les remises appliquées dans la période
    remises_appliquees = PaiementRemise.objects.filter(
        paiement__date_paiement__range=[date_debut, date_fin],
        paiement__statut='VALIDE'
    ).select_related(
        'paiement', 'paiement__eleve', 'paiement__eleve__classe', 
        'paiement__eleve__classe__ecole', 'remise'
    ).order_by('-paiement__date_paiement')
    
    # Statistiques des remises
    stats_remises = {
        'total_remises': remises_appliquees.aggregate(
            total=Sum('montant_remise')
        )['total'] or Decimal('0'),
        'nombre_paiements_avec_remise': remises_appliquees.values('paiement').distinct().count(),
        'nombre_eleves_beneficiaires': remises_appliquees.values('paiement__eleve').distinct().count(),
    }
    
    # Répartition par type de remise
    repartition_types = remises_appliquees.values(
        'remise__nom', 'remise__motif'
    ).annotate(
        total_montant=Sum('montant_remise'),
        nombre_applications=Count('id')
    ).order_by('-total_montant')
    
    # Répartition par école
    repartition_ecoles = remises_appliquees.values(
        'paiement__eleve__classe__ecole__nom'
    ).annotate(
        total_montant=Sum('montant_remise'),
        nombre_applications=Count('id')
    ).order_by('-total_montant')
    
    context = {
        'remises_appliquees': remises_appliquees,
        'stats_remises': stats_remises,
        'repartition_types': repartition_types,
        'repartition_ecoles': repartition_ecoles,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'periode_str': f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    }
    
    return render(request, 'rapports/rapport_remises.html', context)
