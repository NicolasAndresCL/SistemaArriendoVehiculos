"""Enrutado de la API v1.

Un único router para el CRUD de las cinco entidades, más las rutas de
autenticación que no calzan en un ViewSet.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.arriendos.views import DevolucionViewSet, PagoViewSet, ReservaViewSet
from apps.usuarios.views import UsuarioViewSet
from apps.vehiculos.views import VehiculoViewSet

router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuario")
router.register("vehiculos", VehiculoViewSet, basename="vehiculo")
router.register("reservas", ReservaViewSet, basename="reserva")
router.register("pagos", PagoViewSet, basename="pago")
router.register("devoluciones", DevolucionViewSet, basename="devolucion")

urlpatterns = [
    path("auth/", include("apps.usuarios.urls")),
    path("", include(router.urls)),
]
