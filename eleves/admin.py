from django.contrib import admin
from .models import Ecole


@admin.register(Ecole)
class EcoleAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "email", "directeur")
    search_fields = ("nom", "directeur", "telephone", "email")
