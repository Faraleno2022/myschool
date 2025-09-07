from typing import Any
from django.contrib.auth.models import User
from django.db.models import QuerySet


def user_is_admin(user: User) -> bool:
    try:
        return user.is_superuser or (hasattr(user, 'profil') and user.profil.role == 'ADMIN')
    except Exception:
        return user.is_superuser


def user_school(user: User):
    if hasattr(user, 'profil'):
        return user.profil.ecole
    return None


def filter_by_user_school(qs: QuerySet, user: User, field_path: str = 'ecole') -> QuerySet:
    """Filter a queryset by the user's school unless the user is admin.
    field_path can be like 'classe__ecole' or 'enseignant__ecole'.
    """
    # Seul le superutilisateur voit toutes les écoles.
    # Les utilisateurs staff et rôle ADMIN sont filtrés par leur école.
    if getattr(user, 'is_superuser', False):
        return qs
    ecole = user_school(user)
    if ecole is None:
        # If no school is set, return empty queryset to avoid data leakage
        return qs.none()
    return qs.filter(**{field_path: ecole})
