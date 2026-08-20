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
    """Sonda de vida: confirma que el proceso responde y que la BD contesta.

    El job de arranque del CI la consulta para verificar que el sistema no solo
    compila, sino que levanta de verdad.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return Response({"estado": "ok", "base_de_datos": "ok"})
