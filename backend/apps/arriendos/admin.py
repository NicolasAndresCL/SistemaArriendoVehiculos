"""Registro del agregado de arriendo en el panel de administración."""

from django.contrib import admin

from .models import Devolucion, Pago, Reserva


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ["id", "usuario", "vehiculo", "fecha_inicio", "fecha_fin", "estado"]
    list_filter = ["estado"]
    search_fields = ["usuario__email", "vehiculo__patente"]
    inlines = [PagoInline]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ["id", "reserva", "monto", "medio", "estado", "fecha_pago"]
    list_filter = ["medio", "estado"]


@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    list_display = ["id", "reserva", "fecha_devolucion", "dias_atraso", "cargo_adicional"]
    list_filter = ["nivel_combustible"]
