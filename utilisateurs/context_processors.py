from .models import Profil
from .permissions import get_user_permissions, check_comptable_restrictions

def user_context(request):
    """
    Ajoute des informations utilisateur au contexte global
    """
    context = {
        'user_profil': None,
        'user_role': None,
        'user_ecole': None,
        'is_admin': False,
        'user_permissions': {},
        'user_restrictions': {},
    }
    
    if request.user.is_authenticated:
        try:
            profil = request.user.profil
            context.update({
                'user_profil': profil,
                'user_role': profil.role,
                'user_ecole': profil.ecole,
                'is_admin': request.user.is_superuser or profil.role == 'ADMIN',
                'user_permissions': get_user_permissions(request.user),
                'user_restrictions': check_comptable_restrictions(request.user),
            })
        except Profil.DoesNotExist:
            context.update({
                'user_permissions': get_user_permissions(request.user),
                'user_restrictions': check_comptable_restrictions(request.user),
            })
    
    return context
