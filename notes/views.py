from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def tableau_bord(request):
    titre_page = "Tableau de bord - Gestion des notes"
    return render(request, 'notes/dashboard.html', {
        'titre_page': titre_page,
    })
