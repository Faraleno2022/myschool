from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from eleves.models import Eleve
from .models import AbonnementBus
from .forms import AbonnementBusForm
from utilisateurs.utils import user_is_admin, filter_by_user_school
from ecole_moderne.pdf_utils import draw_logo_watermark


@login_required
def tableau_bord(request):
    qs = AbonnementBus.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')

    total = qs.count()
    exp = sum(1 for a in qs if a.est_expire)
    proche = sum(1 for a in qs if a.est_proche_expiration)

    context = {
        'titre_page': 'Abonnements Bus',
        'total': total,
        'exp': exp,
        'proche': proche,
    }
    return render(request, 'bus/tableau_bord.html', context)


@login_required
def liste_abonnements(request):
    qs = AbonnementBus.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')

    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(eleve__nom__icontains=q) |
            Q(eleve__prenom__icontains=q) |
            Q(eleve__matricule__icontains=q) |
            Q(zone__icontains=q) |
            Q(point_arret__icontains=q) |
            Q(contact_parent__icontains=q)
        )

    context = {
        'titre_page': 'Abonnements Bus - Liste',
        'abonnements': qs.order_by('-updated_at')[:500],
        'q': q,
    }
    return render(request, 'bus/liste.html', context)


@login_required
def abonnement_create(request):
    initial = {}
    eleve_id = request.GET.get('eleve')
    if eleve_id:
        try:
            initial['eleve'] = Eleve.objects.get(id=int(eleve_id))
        except Exception:
            pass
    if request.method == 'POST':
        form = AbonnementBusForm(request.POST)
        if form.is_valid():
            abo = form.save()
            messages.success(request, "Abonnement bus créé avec succès.")
            return redirect('bus:liste')
    else:
        form = AbonnementBusForm(initial=initial)
    return render(request, 'bus/form.html', {'form': form, 'titre_page': 'Nouvel abonnement Bus'})


@login_required
def abonnement_edit(request, abo_id):
    abo = get_object_or_404(AbonnementBus, id=abo_id)
    if request.method == 'POST':
        form = AbonnementBusForm(request.POST, instance=abo)
        if form.is_valid():
            form.save()
            messages.success(request, "Abonnement mis à jour.")
            return redirect('bus:liste')
    else:
        form = AbonnementBusForm(instance=abo)
    return render(request, 'bus/form.html', {'form': form, 'titre_page': 'Modifier abonnement Bus'})


@login_required
def relances(request):
    qs = AbonnementBus.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')

    a_relancer = [a for a in qs if a.est_expire or a.est_proche_expiration or a.statut != AbonnementBus.Statut.ACTIF]

    context = {
        'titre_page': 'Relances Abonnements Bus',
        'abonnements': a_relancer,
    }
    return render(request, 'bus/relances.html', context)


@login_required
def export_relances_excel(request):
    qs = AbonnementBus.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
    if not user_is_admin(request.user):
        qs = filter_by_user_school(qs, request.user, 'eleve__classe__ecole')

    data = [a for a in qs if a.est_expire or a.est_proche_expiration or a.statut != AbonnementBus.Statut.ACTIF]

    wb = Workbook(); ws = wb.active; ws.title = 'Relances Bus'
    headers = ['Élève', 'Classe', 'École', 'Périodicité', 'Montant', 'Début', 'Expiration', 'Statut', 'Zone', "Point d'arrêt", 'Contact parent']
    ws.append(headers)
    for a in data:
        el = a.eleve
        ws.append([
            f"{el.prenom} {el.nom} ({el.matricule})",
            getattr(el.classe, 'nom', ''),
            getattr(getattr(el.classe, 'ecole', None), 'nom', ''),
            a.get_periodicite_display(),
            int(a.montant or 0),
            a.date_debut.strftime('%d/%m/%Y') if a.date_debut else '',
            a.date_expiration.strftime('%d/%m/%Y') if a.date_expiration else '',
            a.get_statut_display(),
            a.zone,
            a.point_arret,
            a.contact_parent,
        ])
    widths = [30, 16, 22, 16, 14, 14, 14, 12, 16, 18, 20]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    import io
    stream = io.BytesIO(); wb.save(stream); stream.seek(0)
    resp = HttpResponse(stream.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="relances_bus.xlsx"'
    return resp


@login_required
def generer_recu_abonnement_pdf(request, abo_id):
    """Génère un reçu simple pour un abonnement bus"""
    abo = get_object_or_404(AbonnementBus.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole'), id=abo_id)
    try:
        import io
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from django.contrib.staticfiles import finders
    except Exception:
        messages.error(request, "ReportLab requis (pip install reportlab)")
        return redirect('bus:liste')

    buffer = io.BytesIO(); c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Filigrane standardisé (logo centré, rotation légère, opacité 4%)
    draw_logo_watermark(c, width, height, opacity=0.04, rotate=30, scale=1.5)

    # Titre
    c.setFont('Helvetica-Bold', 16)
    title = 'Reçu Abonnement Bus'
    tw = c.stringWidth(title, 'Helvetica-Bold', 16)
    c.drawString((width - tw)/2, height - 40, title)

    # Corps
    y = height - 80
    c.setFont('Helvetica', 12)
    def line(lbl, val):
        nonlocal y
        c.setFont('Helvetica-Bold', 12); c.drawString(40, y, f"{lbl} :")
        c.setFont('Helvetica', 12); c.drawString(180, y, str(val)); y -= 18

    el = abo.eleve
    line('Élève', f"{el.prenom} {el.nom} ({el.matricule})")
    line('Classe', getattr(el.classe, 'nom', ''))
    line('École', getattr(getattr(el.classe, 'ecole', None), 'nom', ''))
    line('Périodicité', abo.get_periodicite_display())
    line('Montant', f"{int(abo.montant):,}".replace(',', ' ') + ' GNF')
    line('Début', abo.date_debut.strftime('%d/%m/%Y') if abo.date_debut else '')
    line('Expiration', abo.date_expiration.strftime('%d/%m/%Y') if abo.date_expiration else '')
    line('Zone', abo.zone)
    line("Point d'arrêt", abo.point_arret)
    line('Contact parent', abo.contact_parent)

    c.showPage(); c.save(); pdf = buffer.getvalue(); buffer.close()
    resp = HttpResponse(content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename=recu_abonnement_{abo.id}.pdf'
    resp.write(pdf)
    return resp
