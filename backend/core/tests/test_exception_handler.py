"""Tests de `core/api/exception_handler.py`.

El manejador tiene tres caminos: traduce una `ArriendoError` de dominio al
contrato de error de la API, normaliza los errores nativos que DRF ya sabe
producir al mismo contrato, y deja escalar a 500 (devolviendo `None`)
cualquier excepción que no reconozca ninguno de los dos casos anteriores —
porque eso es un bug real, no un error de negocio esperable.
"""

from rest_framework.exceptions import NotFound

from core.api.exception_handler import manejador_de_excepciones
from core.exceptions import FechasInvalidasError, VehiculoNoDisponibleError


def test_convierte_arriendo_error_al_contrato_de_error_de_la_api():
    excepcion = FechasInvalidasError()
    respuesta = manejador_de_excepciones(excepcion, {})
    assert respuesta.status_code == excepcion.http_status
    assert respuesta.data == {
        "error": {
            "codigo": "fechas_invalidas",
            "mensaje": excepcion.mensaje,
            "detalle": {},
        }
    }


def test_convierte_arriendo_error_incluyendo_su_detalle():
    excepcion = VehiculoNoDisponibleError(patente="AA1122")
    respuesta = manejador_de_excepciones(excepcion, {})
    assert respuesta.data["error"]["detalle"] == {"patente": "AA1122"}


def test_normaliza_not_found_de_drf_al_contrato_con_codigo_no_encontrado():
    respuesta = manejador_de_excepciones(NotFound(), {})
    assert respuesta.status_code == 404
    assert respuesta.data["error"]["codigo"] == "no_encontrado"
    assert "mensaje" in respuesta.data["error"]


def test_excepcion_no_reconocida_devuelve_none_para_escalar_a_500():
    resultado = manejador_de_excepciones(ValueError("bug real, no error de negocio"), {})
    assert resultado is None
