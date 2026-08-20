"""Registro de usuarios en el panel de administración de Django."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["apellido", "nombre"]
    list_display = ["email", "nombre", "apellido", "rut", "rol", "is_active", "is_staff"]
    list_filter = ["rol", "is_active", "is_staff"]
    search_fields = ["email", "rut", "nombre", "apellido"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("rut", "nombre", "apellido", "telefono", "rol")}),
        ("Licencia de conducir", {"fields": ("licencia_numero", "licencia_vencimiento")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "rut", "nombre", "apellido", "password1", "password2"),
            },
        ),
    )
