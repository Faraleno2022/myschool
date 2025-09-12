"""
URL configuration for ecole_moderne project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views.decorators.cache import cache_control

# Fonction pour servir le favicon
@cache_control(max_age=60 * 60 * 24, immutable=True, public=True)
def favicon_view(request):
    return HttpResponse(status=204)  # No Content

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('index/', TemplateView.as_view(template_name='home.html'), name='index'),
    path('favicon.ico', favicon_view, name='favicon'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),
    
    # Inscription et gestion multi-tenant des écoles
    path('ecole/', include('inscription_ecoles.urls')),
    
    # Modules principaux
    path('eleves/', include('eleves.urls')),
    path('paiements/', include('paiements.urls')),
    path('depenses/', include('depenses.urls')),
    path('salaires/', include('salaires.urls')),
    path('administration/', include('administration.urls')),
    path('utilisateurs/', include('utilisateurs.urls')),
    path('rapports/', include('rapports.urls')),
    path('bus/', include('bus.urls')),
    path('notes/', include('notes.urls')),
]

# Servir les fichiers STATIC et MEDIA en développement
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
