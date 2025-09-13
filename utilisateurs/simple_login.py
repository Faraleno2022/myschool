"""
Vue de login simplifiée pour diagnostiquer l'erreur 500
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache

@csrf_protect
@never_cache
def simple_login(request):
    """Vue de login simplifiée sans sécurité avancée"""
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active:
                login(request, user)
                next_url = request.GET.get('next')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect('eleves:liste_eleves')
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
        else:
            messages.error(request, 'Nom d\'utilisateur et mot de passe requis.')
    
    return render(request, 'utilisateurs/login.html')
