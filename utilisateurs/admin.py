from django.contrib import admin
from .models import Profil


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'telephone', 'ecole', 'actif')
    list_filter = ('role', 'ecole', 'actif')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'telephone')
    autocomplete_fields = ('user', 'ecole')
