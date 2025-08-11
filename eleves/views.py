from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from .models import Eleve, Responsable, Classe, Ecole, HistoriqueEleve
from .forms import EleveForm, ResponsableForm, RechercheEleveForm, ClasseForm
from utilisateurs.models import JournalActivite
from utilisateurs.utils import user_is_admin, filter_by_user_school, user_school

@login_required
def liste_eleves(request):
    """Vue pour afficher la liste des élèves avec recherche et filtres"""
    form_recherche = RechercheEleveForm(request.GET or None)
    
    # Requête de base avec optimisation
    eleves = Eleve.objects.select_related(
        'classe', 'classe__ecole', 'responsable_principal', 'responsable_secondaire'
    ).prefetch_related('paiements')
    # Filtrage par école pour non-admin
    if not user_is_admin(request.user):
        eleves = filter_by_user_school(eleves, request.user, 'classe__ecole')
    
    # Application du filtre simple (recherche globale multi-critères)
    if form_recherche.is_valid():
        recherche = form_recherche.cleaned_data.get('recherche')
        if recherche:
            eleves = eleves.filter(
                Q(matricule__icontains=recherche) |
                Q(nom__icontains=recherche) |
                Q(prenom__icontains=recherche) |
                Q(classe__nom__icontains=recherche) |
                Q(classe__ecole__nom__icontains=recherche) |
                Q(responsable_principal__nom__icontains=recherche) |
                Q(responsable_principal__prenom__icontains=recherche) |
                Q(responsable_secondaire__nom__icontains=recherche) |
                Q(responsable_secondaire__prenom__icontains=recherche)
            )
    
    # Statistiques
    stats = {
        'total_eleves': eleves.count(),
        'eleves_actifs': eleves.filter(statut='ACTIF').count(),
        'eleves_suspendus': eleves.filter(statut='SUSPENDU').count(),
    }
    
    # Pagination
    paginator = Paginator(eleves.order_by('nom', 'prenom'), 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Log de l'activité
    JournalActivite.objects.create(
        user=request.user,
        action='CONSULTATION',
        type_objet='ELEVE',
        description=f"Consultation de la liste des élèves (page {page_number or 1})",
        adresse_ip=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    context = {
        'page_obj': page_obj,
        'form_recherche': form_recherche,
        'stats': stats,
        'titre_page': 'Gestion des Élèves'
    }

    # Rendu partiel pour la recherche dynamique
    if request.GET.get('partial') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response = render(request, 'eleves/partials/_liste_eleves_zone.html', context)
        # Eviter le cache sur le fragment
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    response = render(request, 'eleves/liste_eleves.html', context)
    
    # Headers anti-cache pour s'assurer que la liste est toujours fraîche
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

@login_required
def detail_eleve(request, eleve_id):
    """Vue pour afficher les détails d'un élève"""
    qs = Eleve.objects.select_related(
        'classe', 'classe__ecole', 'responsable_principal', 'responsable_secondaire'
    ).prefetch_related('paiements', 'historique')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'classe__ecole')
    eleve = get_object_or_404(qs, id=eleve_id)
    
    # Statistiques des paiements
    paiements_stats = {
        'total_paiements': eleve.paiements.count(),
        'paiements_valides': eleve.paiements.filter(statut='VALIDE').count(),
        'montant_total': sum(p.montant for p in eleve.paiements.filter(statut='VALIDE')),
    }
    
    # Historique récent
    historique_recent = eleve.historique.all()[:10]
    
    # Log de l'activité
    JournalActivite.objects.create(
        user=request.user,
        action='CONSULTATION',
        type_objet='ELEVE',
        objet_id=eleve.id,
        description=f"Consultation du profil de {eleve.nom_complet}",
        adresse_ip=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    context = {
        'eleve': eleve,
        'paiements_stats': paiements_stats,
        'historique_recent': historique_recent,
        'titre_page': f'Profil de {eleve.nom_complet}'
    }
    
    return render(request, 'eleves/detail_eleve.html', context)

@login_required
def ajouter_eleve(request):
    """Vue pour ajouter un nouvel élève"""
    # Si l'utilisateur n'est pas admin et n'a pas d'école associée, refuser l'accès
    if not user_is_admin(request.user) and user_school(request.user) is None:
        return render(request, 'utilisateurs/acces_refuse_ecole.html', status=403)
    if request.method == 'POST':
        form = EleveForm(request.POST, request.FILES)
        # Restreindre les classes au périmètre de l'école pour non-admin
        if not user_is_admin(request.user):
            try:
                form.fields['classe'].queryset = Classe.objects.filter(ecole=user_school(request.user))
            except Exception:
                pass
        
        # Gestion des nouveaux responsables
        responsable_principal_form = None
        responsable_secondaire_form = None
        
        # Vérifier si on doit créer de nouveaux responsables
        creer_resp_principal = request.POST.get('responsable_principal_nouveau') == 'on'
        creer_resp_secondaire = request.POST.get('responsable_secondaire_nouveau') == 'on'
        
        if creer_resp_principal:
            responsable_principal_form = ResponsableForm(request.POST, prefix='resp_principal')
        
        if creer_resp_secondaire:
            responsable_secondaire_form = ResponsableForm(request.POST, prefix='resp_secondaire')
        
        # Validation du formulaire principal
        form_valide = form.is_valid()
        
        # Validation des formulaires de responsables
        resp_principal_valide = True
        resp_secondaire_valide = True
        
        if responsable_principal_form:
            resp_principal_valide = responsable_principal_form.is_valid()
        
        if responsable_secondaire_form:
            resp_secondaire_valide = responsable_secondaire_form.is_valid()
        
        # Vérifier qu'un responsable principal est fourni (seulement si le formulaire principal est valide)
        if form_valide:
            if not creer_resp_principal and not form.cleaned_data.get('responsable_principal'):
                form.add_error('responsable_principal', 'Un responsable principal est obligatoire.')
                form_valide = False
        
        if form_valide and resp_principal_valide and resp_secondaire_valide:
            try:
                # Créer les responsables si nécessaire
                if responsable_principal_form:
                    responsable_principal = responsable_principal_form.save()
                    form.instance.responsable_principal = responsable_principal
                
                if responsable_secondaire_form:
                    responsable_secondaire = responsable_secondaire_form.save()
                    form.instance.responsable_secondaire = responsable_secondaire
                
                # Sauvegarder l'élève
                eleve = form.save(commit=False)
                eleve.cree_par = request.user
                eleve.save()
                
                # Créer l'historique
                HistoriqueEleve.objects.create(
                    eleve=eleve,
                    action='CREATION',
                    description=f"Création du profil de {eleve.prenom} {eleve.nom}",
                    utilisateur=request.user
                )
                
                # Log de l'activité
                JournalActivite.objects.create(
                    user=request.user,
                    action='CREATION',
                    type_objet='ELEVE',
                    objet_id=eleve.id,
                    description=f"Création de l'élève {eleve.prenom} {eleve.nom} (matricule: {eleve.matricule})",
                    adresse_ip=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                messages.success(request, f"L'élève {eleve.prenom} {eleve.nom} a été ajouté avec succès.")
                return redirect('eleves:detail_eleve', eleve_id=eleve.id)
                
            except Exception as e:
                messages.error(request, f"Erreur lors de l'enregistrement : {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = EleveForm()
        if not user_is_admin(request.user):
            try:
                form.fields['classe'].queryset = Classe.objects.filter(ecole=user_school(request.user))
            except Exception:
                pass
        responsable_principal_form = ResponsableForm(prefix='resp_principal')
        responsable_secondaire_form = ResponsableForm(prefix='resp_secondaire')
    
    # Statistiques pour l'affichage
    eleves = Eleve.objects.filter(cree_par=request.user)
    stats = {
        'total_eleves': eleves.count(),
        'eleves_actifs': eleves.filter(statut='ACTIF').count(),
        'eleves_exclus': eleves.filter(statut='EXCLU').count(),
    }
    
    context = {
        'form': form,
        'responsable_principal_form': responsable_principal_form,
        'responsable_secondaire_form': responsable_secondaire_form,
        'stats': stats,
        'titre_page': 'Ajouter un Élève',
        'action': 'Ajouter'
    }
    
    return render(request, 'eleves/ajouter_eleve.html', context)

@login_required
def modifier_eleve(request, eleve_id):
    """Vue pour modifier un élève existant"""
    qs = Eleve.objects.all()
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'classe__ecole')
    eleve = get_object_or_404(qs, id=eleve_id)
    
    if request.method == 'POST':
        form = EleveForm(request.POST, request.FILES, instance=eleve)
        if not user_is_admin(request.user):
            try:
                form.fields['classe'].queryset = Classe.objects.filter(ecole=user_school(request.user))
            except Exception:
                pass
        
        if form.is_valid():
            # Détecter les changements
            changements = []
            for field in form.changed_data:
                if field in form.fields:
                    ancien_val = getattr(eleve, field, '')
                    nouveau_val = form.cleaned_data[field]
                    changements.append(f"{form.fields[field].label}: {ancien_val} → {nouveau_val}")
            
            eleve = form.save()
            
            # Créer l'historique si des changements ont été effectués
            if changements:
                HistoriqueEleve.objects.create(
                    eleve=eleve,
                    action='MODIFICATION',
                    description=f"Modification: {', '.join(changements)}",
                    utilisateur=request.user
                )
                
                # Log de l'activité
                JournalActivite.objects.create(
                    user=request.user,
                    action='MODIFICATION',
                    type_objet='ELEVE',
                    objet_id=eleve.id,
                    description=f"Modification de l'élève {eleve.nom_complet}: {', '.join(changements)}",
                    adresse_ip=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            
            # Message de succès détaillé
            if changements:
                nb_changements = len(changements)
                message_changements = f" ({nb_changements} modification{'s' if nb_changements > 1 else ''} effectuée{'s' if nb_changements > 1 else ''})"
                messages.success(
                    request, 
                    f"✅ Les informations de {eleve.prenom} {eleve.nom} ont été mises à jour avec succès{message_changements}."
                )
            else:
                messages.info(request, f"ℹ️ Aucune modification détectée pour {eleve.prenom} {eleve.nom}.")
            
            # Rediriger vers la liste si demandé, sinon vers le détail
            action = request.POST.get('action', 'save')
            if action == 'save_and_list' or request.POST.get('redirect_to_list'):
                return redirect('eleves:liste_eleves')
            else:
                return redirect('eleves:detail_eleve', eleve_id=eleve.id)
        else:
            # Formulaire invalide: informer l'utilisateur des erreurs
            # Construire un résumé concis des erreurs (limité pour l'UI)
            erreurs = []
            try:
                for champ, msgs in list(form.errors.items())[:5]:
                    libelle = form.fields.get(champ).label if champ in form.fields else champ
                    erreurs.append(f"{libelle}: {', '.join([str(m) for m in msgs])}")
            except Exception:
                pass
            if erreurs:
                messages.error(request, "Le formulaire contient des erreurs: " + " | ".join(erreurs))
            else:
                messages.error(request, "Le formulaire est invalide. Veuillez corriger les erreurs et réessayer.")
    else:
        form = EleveForm(instance=eleve)
        if not user_is_admin(request.user):
            try:
                form.fields['classe'].queryset = Classe.objects.filter(ecole=user_school(request.user))
            except Exception:
                pass
    
    context = {
        'form': form,
        'eleve': eleve,
        'titre_page': f'Modifier {eleve.nom_complet}',
        'action': 'Modifier'
    }
    
    return render(request, 'eleves/modifier_eleve.html', context)

@login_required
@require_http_methods(["POST"])
def supprimer_eleve(request, eleve_id):
    """Vue pour supprimer un élève (soft delete)"""
    qs = Eleve.objects.all()
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'classe__ecole')
    eleve = get_object_or_404(qs, id=eleve_id)
    
    # Vérifier s'il y a des paiements associés
    if eleve.paiements.exists():
        messages.error(request, "Impossible de supprimer cet élève car il a des paiements associés.")
        return redirect('eleves:detail_eleve', eleve_id=eleve.id)
    
    nom_complet = f"{eleve.prenom} {eleve.nom}"
    matricule = eleve.matricule
    
    # Soft delete - changer le statut au lieu de supprimer
    eleve.statut = 'EXCLU'
    eleve.save()
    
    # Créer l'historique
    HistoriqueEleve.objects.create(
        eleve=eleve,
        action='EXCLUSION',
        description=f"Exclusion de l'élève {nom_complet}",
        utilisateur=request.user
    )
    
    # Log de l'activité
    JournalActivite.objects.create(
        user=request.user,
        action='SUPPRESSION',
        type_objet='ELEVE',
        objet_id=eleve.id,
        description=f"Exclusion de l'élève {nom_complet} (matricule: {matricule})",
        adresse_ip=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    messages.success(request, f"L'élève {nom_complet} a été exclu.")
    return redirect('eleves:liste_eleves')

@login_required
def gestion_classes(request):
    """Vue pour gérer les classes"""
    classes = Classe.objects.select_related('ecole').annotate(
        nombre_eleves=Count('eleves')
    ).order_by('ecole__nom', 'niveau', 'nom')
    if not user_is_admin(request.user):
        classes = classes.filter(ecole=user_school(request.user))
    
    # Statistiques
    stats = {
        'total_classes': classes.count(),
        'total_eleves': sum(c.nombre_eleves for c in classes),
        'classes_par_ecole': {}
    }
    
    ecoles_iter = Ecole.objects.all()
    if not user_is_admin(request.user):
        ecoles_iter = ecoles_iter.filter(id=user_school(request.user).id)
    for ecole in ecoles_iter:
        classes_ecole = classes.filter(ecole=ecole)
        stats['classes_par_ecole'][ecole.nom] = {
            'nombre_classes': classes_ecole.count(),
            'nombre_eleves': sum(c.nombre_eleves for c in classes_ecole)
        }
    
    context = {
        'classes': classes,
        'stats': stats,
        'titre_page': 'Gestion des Classes'
    }
    
    return render(request, 'eleves/gestion_classes.html', context)

@login_required
def ajax_classes_par_ecole(request, ecole_id):
    """Vue AJAX pour récupérer les classes d'une école"""
    try:
        # Non-admin: ne peut demander que sa propre école
        if not user_is_admin(request.user):
            if str(user_school(request.user).id) != str(ecole_id):
                return JsonResponse({'success': False, 'error': "Accès non autorisé à cette école."}, status=403)
        ecole = get_object_or_404(Ecole, id=ecole_id)
        classes = Classe.objects.filter(ecole=ecole).values('id', 'nom')
        return JsonResponse({
            'success': True,
            'classes': list(classes)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def ajax_statistiques_eleves(request):
    """Vue AJAX pour récupérer les statistiques des élèves"""
    try:
        if user_is_admin(request.user):
            eleves = Eleve.objects.all()
        else:
            eleves = Eleve.objects.filter(classe__ecole=user_school(request.user))
        stats = {
            'total_eleves': eleves.count(),
            'eleves_actifs': eleves.filter(statut='ACTIF').count(),
            'eleves_exclus': eleves.filter(statut='EXCLU').count(),
        }
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def statistiques_eleves(request):
    """Vue pour afficher les statistiques complètes des élèves"""
    from django.db.models import Sum, Avg, Max, Min
    from datetime import datetime, date
    from dateutil.relativedelta import relativedelta
    
    # 1. STATISTIQUES GÉNÉRALES
    if user_is_admin(request.user):
        eleves_base = Eleve.objects.all()
        classes_base = Classe.objects.all()
        responsables_base = Responsable.objects.all()
        ecoles_base = Ecole.objects.all()
    else:
        ecole_u = user_school(request.user)
        eleves_base = Eleve.objects.filter(classe__ecole=ecole_u)
        classes_base = Classe.objects.filter(ecole=ecole_u)
        responsables_base = Responsable.objects.all()
        ecoles_base = Ecole.objects.filter(id=ecole_u.id)
    total_eleves = eleves_base.count()
    stats_generales = {
        'total_eleves': total_eleves,
        'eleves_actifs': eleves_base.filter(statut='ACTIF').count(),
        'eleves_suspendus': eleves_base.filter(statut='SUSPENDU').count(),
        'eleves_exclus': eleves_base.filter(statut='EXCLU').count(),
        'eleves_transferes': eleves_base.filter(statut='TRANSFERE').count(),
        'eleves_diplomes': eleves_base.filter(statut='DIPLOME').count(),
        'total_ecoles': ecoles_base.count(),
        'total_classes': classes_base.count(),
        'total_responsables': responsables_base.count(),
    }
    
    # 2. STATISTIQUES DÉMOGRAPHIQUES
    stats_demographiques = {
        'garcons': eleves_base.filter(sexe='M').count(),
        'filles': eleves_base.filter(sexe='F').count(),
        'pourcentage_garcons': 0,
        'pourcentage_filles': 0,
    }
    
    if total_eleves > 0:
        stats_demographiques['pourcentage_garcons'] = round((stats_demographiques['garcons'] / total_eleves) * 100, 1)
        stats_demographiques['pourcentage_filles'] = round((stats_demographiques['filles'] / total_eleves) * 100, 1)
    
    # 3. STATISTIQUES D'ÂGE
    eleves_avec_age = eleves_base.exclude(date_naissance__isnull=True)
    ages = []
    for eleve in eleves_avec_age:
        age = relativedelta(date.today(), eleve.date_naissance).years
        ages.append(age)
    
    stats_age = {
        'age_moyen': round(sum(ages) / len(ages), 1) if ages else 0,
        'age_min': min(ages) if ages else 0,
        'age_max': max(ages) if ages else 0,
        'eleves_moins_10': len([a for a in ages if a < 10]),
        'eleves_10_15': len([a for a in ages if 10 <= a <= 15]),
        'eleves_plus_15': len([a for a in ages if a > 15]),
    }
    
    # 4. RÉPARTITION PAR ÉCOLE (détaillée)
    stats_par_ecole = []
    for ecole in ecoles_base:
        eleves_ecole = eleves_base.filter(classe__ecole=ecole)
        classes_ecole = classes_base.filter(ecole=ecole)
        
        ecole_stats = {
            'ecole': ecole,
            'total_eleves': eleves_ecole.count(),
            'eleves_actifs': eleves_ecole.filter(statut='ACTIF').count(),
            'garcons': eleves_ecole.filter(sexe='M').count(),
            'filles': eleves_ecole.filter(sexe='F').count(),
            'total_classes': classes_ecole.count(),
            'classes_actives': classes_ecole.filter(eleves__isnull=False).distinct().count(),
            'moyenne_eleves_par_classe': 0,
        }
        
        if ecole_stats['total_classes'] > 0:
            ecole_stats['moyenne_eleves_par_classe'] = round(ecole_stats['total_eleves'] / ecole_stats['total_classes'], 1)
        
        # Pourcentages pour cette école
        if ecole_stats['total_eleves'] > 0:
            ecole_stats['pourcentage_garcons'] = round((ecole_stats['garcons'] / ecole_stats['total_eleves']) * 100, 1)
            ecole_stats['pourcentage_filles'] = round((ecole_stats['filles'] / ecole_stats['total_eleves']) * 100, 1)
        else:
            ecole_stats['pourcentage_garcons'] = 0
            ecole_stats['pourcentage_filles'] = 0
        
        stats_par_ecole.append(ecole_stats)
    
    # 5. RÉPARTITION PAR NIVEAU (détaillée)
    stats_par_niveau = []
    total_pour_pourcentage = total_eleves if total_eleves > 0 else 1
    
    for niveau_code, niveau_nom in Classe.NIVEAUX_CHOICES:
        eleves_niveau = eleves_base.filter(classe__niveau=niveau_code)
        count = eleves_niveau.count()
        
        if count > 0:
            niveau_stats = {
                'niveau_code': niveau_code,
                'niveau_nom': niveau_nom,
                'total_eleves': count,
                'garcons': eleves_niveau.filter(sexe='M').count(),
                'filles': eleves_niveau.filter(sexe='F').count(),
                'actifs': eleves_niveau.filter(statut='ACTIF').count(),
                'pourcentage': round((count / total_pour_pourcentage) * 100, 1),
                'classes': Classe.objects.filter(niveau=niveau_code, eleves__isnull=False).distinct().count(),
            }
            stats_par_niveau.append(niveau_stats)
    
    # 6. STATISTIQUES PAR CLASSE (top 10)
    stats_par_classe = []
    classes_avec_eleves = classes_base.annotate(
        nb_eleves=Count('eleves')
    ).filter(nb_eleves__gt=0).order_by('-nb_eleves')[:10]
    
    for classe in classes_avec_eleves:
        eleves_classe = eleves_base.filter(classe=classe)
        classe_stats = {
            'classe': classe,
            'total_eleves': eleves_classe.count(),
            'garcons': eleves_classe.filter(sexe='M').count(),
            'filles': eleves_classe.filter(sexe='F').count(),
            'actifs': eleves_classe.filter(statut='ACTIF').count(),
        }
        stats_par_classe.append(classe_stats)
    
    # 7. STATISTIQUES TEMPORELLES
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    stats_temporelles = {
        'inscriptions_cette_annee': Eleve.objects.filter(date_inscription__year=current_year).count(),
        'inscriptions_ce_mois': Eleve.objects.filter(
            date_inscription__year=current_year,
            date_inscription__month=current_month
        ).count(),
        'inscriptions_cette_semaine': Eleve.objects.filter(
            date_inscription__gte=date.today() - relativedelta(days=7)
        ).count(),
    }
    
    # Évolution mensuelle (6 derniers mois)
    evolution_mensuelle = []
    for i in range(6):
        mois_date = date.today() - relativedelta(months=i)
        nb_inscriptions = Eleve.objects.filter(
            date_inscription__year=mois_date.year,
            date_inscription__month=mois_date.month
        ).count()
        
        evolution_mensuelle.append({
            'mois': mois_date.strftime('%B %Y'),
            'mois_court': mois_date.strftime('%b'),
            'inscriptions': nb_inscriptions
        })
    
    evolution_mensuelle.reverse()  # Du plus ancien au plus récent
    
    # 8. STATISTIQUES DE RESPONSABLES
    stats_responsables = {
        'total_responsables': responsables_base.count(),
        'responsables_principaux': eleves_base.values('responsable_principal').distinct().count(),
        'responsables_secondaires': eleves_base.filter(responsable_secondaire__isnull=False).values('responsable_secondaire').distinct().count(),
        'eleves_avec_deux_responsables': eleves_base.filter(responsable_secondaire__isnull=False).count(),
        'eleves_avec_un_responsable': eleves_base.filter(responsable_secondaire__isnull=True).count(),
    }
    
    # Répartition par relation
    relations_stats = []
    for relation_code, relation_nom in Responsable.RELATION_CHOICES:
        count = Responsable.objects.filter(relation=relation_code).count()
        if count > 0:
            relations_stats.append({
                'relation': relation_nom,
                'count': count,
                'pourcentage': round((count / stats_responsables['total_responsables']) * 100, 1) if stats_responsables['total_responsables'] > 0 else 0
            })
    
    # 9. STATISTIQUES FINANCIÈRES (basiques)
    from paiements.models import Paiement
    
    paiements_qs = Paiement.objects.all()
    if not user_is_admin(request.user):
        paiements_qs = paiements_qs.filter(eleve__classe__ecole=user_school(request.user))
    stats_financieres = {
        'eleves_avec_paiements': eleves_base.filter(paiements__isnull=False).distinct().count(),
        'eleves_sans_paiements': eleves_base.filter(paiements__isnull=True).count(),
        'total_paiements': paiements_qs.count(),
        'paiements_valides': paiements_qs.filter(statut='VALIDE').count(),
        'paiements_en_attente': paiements_qs.filter(statut='EN_ATTENTE').count(),
    }
    
    if stats_financieres['total_paiements'] > 0:
        stats_financieres['taux_validation'] = round(
            (stats_financieres['paiements_valides'] / stats_financieres['total_paiements']) * 100, 1
        )
    else:
        stats_financieres['taux_validation'] = 0
    
    # 10. INDICATEURS DE PERFORMANCE
    indicateurs = {
        'taux_activite': round((stats_generales['eleves_actifs'] / total_eleves) * 100, 1) if total_eleves > 0 else 0,
        'taux_retention': round(((total_eleves - stats_generales['eleves_exclus'] - stats_generales['eleves_transferes']) / total_eleves) * 100, 1) if total_eleves > 0 else 0,
        'ratio_eleves_classes': round(total_eleves / stats_generales['total_classes'], 1) if stats_generales['total_classes'] > 0 else 0,
        'ratio_eleves_responsables': round(total_eleves / stats_responsables['total_responsables'], 1) if stats_responsables['total_responsables'] > 0 else 0,
    }
    
    context = {
        'stats_generales': stats_generales,
        'stats_demographiques': stats_demographiques,
        'stats_age': stats_age,
        'stats_par_ecole': stats_par_ecole,
        'stats_par_niveau': stats_par_niveau,
        'stats_par_classe': stats_par_classe,
        'stats_temporelles': stats_temporelles,
        'evolution_mensuelle': evolution_mensuelle,
        'stats_responsables': stats_responsables,
        'relations_stats': relations_stats,
        'stats_financieres': stats_financieres,
        'indicateurs': indicateurs,
        'titre_page': 'Statistiques Complètes des Élèves'
    }
    
    return render(request, 'eleves/statistiques.html', context)
