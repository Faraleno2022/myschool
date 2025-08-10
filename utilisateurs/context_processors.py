from .models import Profil
from .utils import user_is_admin, user_school


def utilisateur_contexte(request):
    user = request.user if hasattr(request, 'user') else None
    profil = getattr(user, 'profil', None) if user and user.is_authenticated else None
    return {
        'current_user': user,
        'current_profil': profil,
        'current_ecole': user_school(user) if user and user.is_authenticated else None,
        'is_admin': user_is_admin(user) if user and user.is_authenticated else False,
    }
