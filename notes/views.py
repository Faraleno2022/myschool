from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from eleves.models import Classe
from utilisateurs.utils import filter_by_user_school, user_school
from ecole_moderne.security_decorators import admin_required
from .forms import ClasseNotesForm, MatiereClasseForm
from .models import MatiereClasse


# Groupes de niveaux pour l'affichage
PRIMAIRE = {
    'PRIMAIRE_1', 'PRIMAIRE_2', 'PRIMAIRE_3', 'PRIMAIRE_4', 'PRIMAIRE_5', 'PRIMAIRE_6'
}
COLLEGE = {
    'COLLEGE_7', 'COLLEGE_8', 'COLLEGE_9', 'COLLEGE_10'
}
LYCEE = {
    'LYCEE_11', 'LYCEE_12', 'TERMINALE'
}


@login_required
def tableau_bord(request):
    """Tableau de bord des notes: liste les classes par groupe de niveaux.
    Filtré par l'école de l'utilisateur (sauf admin).
    """
    classes_qs = filter_by_user_school(Classe.objects.all().order_by('niveau', 'nom'), request.user, 'ecole')

    def group_classes(qs):
        primaire, college, lycee = [], [], []
        for c in qs:
            if c.niveau in PRIMAIRE:
                primaire.append(c)
            elif c.niveau in COLLEGE:
                college.append(c)
            elif c.niveau in LYCEE:
                lycee.append(c)
        return primaire, college, lycee

    primaire, college, lycee = group_classes(classes_qs)

    context = {
        'classes_primaire': primaire,
        'classes_college': college,
        'classes_lycee': lycee,
    }
    return render(request, 'notes/dashboard.html', context)


@admin_required
def creer_classe(request, niveau):
    """Créer une classe pour un niveau donné dans l'école de l'utilisateur."""
    if request.method == 'POST':
        form = ClasseNotesForm(request.POST, niveau_initial=niveau)
        if form.is_valid():
            classe = form.save(commit=False)
            classe.ecole = user_school(request.user)
            if classe.ecole is None:
                messages.error(request, "Aucune école associée à votre compte.")
                return redirect('notes:tableau_bord')
            classe.save()
            messages.success(request, f"Classe '{classe.nom}' créée avec succès.")
            return redirect('notes:tableau_bord')
    else:
        form = ClasseNotesForm(niveau_initial=niveau)
    return render(request, 'notes/classe_form.html', {'form': form, 'niveau': niveau})


@admin_required
def supprimer_classe(request, classe_id):
    """Supprimer une classe si elle appartient à l'école de l'utilisateur et qu'elle est vide."""
    classe = get_object_or_404(filter_by_user_school(Classe.objects.all(), request.user, 'ecole'), pk=classe_id)
    if request.method == 'POST':
        if hasattr(classe, 'eleves') and classe.eleves.exists():
            messages.error(request, "Impossible de supprimer une classe qui contient des élèves.")
            return redirect('notes:tableau_bord')
        classe.delete()
        messages.success(request, "Classe supprimée avec succès.")
        return redirect('notes:tableau_bord')
    return render(request, 'notes/confirm_delete.html', {
        'objet': classe,
        'message': "Confirmez-vous la suppression de cette classe ? (Cette action est irréversible)",
        'action_url': reverse('notes:supprimer_classe', args=[classe.id])
    })


@admin_required
def matieres_classe(request, classe_id):
    """Liste et gestion des matières d'une classe."""
    classe = get_object_or_404(filter_by_user_school(Classe.objects.all(), request.user, 'ecole'), pk=classe_id)
    matieres = MatiereClasse.objects.filter(classe=classe, ecole=classe.ecole).order_by('nom')
    return render(request, 'notes/matieres_classe.html', {
        'classe': classe,
        'matieres': matieres,
    })


@admin_required
def creer_matiere(request, classe_id):
    """Créer une matière pour une classe donnée."""
    classe = get_object_or_404(filter_by_user_school(Classe.objects.all(), request.user, 'ecole'), pk=classe_id)
    if request.method == 'POST':
        form = MatiereClasseForm(request.POST)
        if form.is_valid():
            mat = form.save(commit=False)
            mat.classe = classe
            mat.ecole = classe.ecole
            try:
                mat.save()
                messages.success(request, f"Matière '{mat.nom}' ajoutée.")
                return redirect('notes:matieres_classe', classe.id)
            except Exception as e:
                messages.error(request, f"Erreur lors de la création: {e}")
    else:
        form = MatiereClasseForm()
    return render(request, 'notes/matiere_form.html', {'form': form, 'classe': classe})


@admin_required
def supprimer_matiere(request, pk):
    """Supprimer une matière de classe."""
    matiere = get_object_or_404(filter_by_user_school(MatiereClasse.objects.select_related('classe', 'ecole'), request.user, 'ecole'), pk=pk)
    if request.method == 'POST':
        classe_id = matiere.classe_id
        matiere.delete()
        messages.success(request, "Matière supprimée.")
        return redirect('notes:matieres_classe', classe_id)
    return render(request, 'notes/confirm_delete.html', {
        'objet': matiere,
        'message': "Confirmez-vous la suppression de cette matière ?",
        'action_url': reverse('notes:supprimer_matiere', args=[matiere.id])
    })
