"""Vistas transversales que no pertenecen a ninguna app de dominio."""

from django.db import connection
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def salud(request: Request) -> Response:
    """Sonda de disponibilidad: el proceso responde y la base de datos contesta.

    La consultan el job de arranque del CI (para verificar que el sistema no
    solo compila, sino que levanta de verdad), el HEALTHCHECK de la imagen y la
    ``readinessProbe`` de Kubernetes: si la base no responde, el pod deja de
    recibir tráfico pero sigue vivo.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return Response({"estado": "ok", "base_de_datos": "ok"})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def vivo(request: Request) -> Response:
    """Sonda de vida: solo confirma que el proceso atiende peticiones.

    Es la que consume la ``livenessProbe`` de Kubernetes, y a propósito NO toca
    la base de datos: una liveness que dependiera de ella reiniciaría todas las
    réplicas a la vez cuando el problema no fuera de ellas, convirtiendo una
    avería externa en un apagón propio.
    """
    return Response({"estado": "ok"})
