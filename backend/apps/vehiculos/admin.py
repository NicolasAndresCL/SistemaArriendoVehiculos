"""Registro de vehículos en el panel de administración."""

from django.contrib import admin

from .models import Vehiculo


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ["patente", "marca", "modelo", "anio", "categoria", "tarifa_diaria", "estado"]
    list_filter = ["estado", "categoria", "transmision", "combustible"]
    search_fields = ["patente", "marca", "modelo"]
