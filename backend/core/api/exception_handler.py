"""Manejador único de excepciones de la API.

Traduce las excepciones de dominio a HTTP y normaliza también los errores
nativos de DRF al mismo contrato, para que el frontend tenga una sola forma de
leer un error:

    {"error": {"codigo": "...", "mensaje": "...", "detalle": {...}}}

El `codigo` es el identificador estable que consume el cliente. El `mensaje` en
español puede cambiar sin romper a nadie.
"""

import logging

from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as manejador_drf

from core.exceptions import ArriendoError

logger = logging.getLogger(__name__)

# Códigos estables para los errores que DRF ya sabe producir.
_CODIGOS_DRF = {
    400: "peticion_invalida",
    401: "no_autenticado",
    403: "sin_permiso",
    404: "no_encontrado",
    405: "metodo_no_permitido",
    409: "conflicto",
    429: "demasiadas_peticiones",
}


def manejador_de_excepciones(exc: Exception, context: dict) -> Response | None:
    """Punto de entrada configurado en `REST_FRAMEWORK['EXCEPTION_HANDLER']`."""
    if isinstance(exc, ArriendoError):
        # Error de negocio: esperable, se registra como warning.
        logger.warning("Regla de negocio rechazó la operación: %s (%s)", exc.mensaje, exc.codigo)
        return Response(
            {"error": {"codigo": exc.codigo, "mensaje": exc.mensaje, "detalle": exc.detalle()}},
            status=exc.http_status,
        )

    respuesta = manejador_drf(exc, context)
    if respuesta is None:
        # Nadie lo reconoce: es un bug real y debe verse ruidoso, nunca
        # tragarse en silencio. Devolver None deja que Django produzca el 500.
        logger.exception("Excepción no controlada en la API")
        return None

    codigo = _CODIGOS_DRF.get(respuesta.status_code, "error_api")
    respuesta.data = {
        "error": {
            "codigo": codigo,
            "mensaje": _mensaje_legible(exc, respuesta.data),
            "detalle": respuesta.data if isinstance(respuesta.data, dict) else {},
        }
    }
    return respuesta


def _mensaje_legible(exc: Exception, data: object) -> str:
    """Extrae un texto en español presentable desde el detalle de DRF."""
    if isinstance(exc, exceptions.ValidationError):
        return "Hay campos con errores de validación."
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])
    return "No se pudo completar la operación."
