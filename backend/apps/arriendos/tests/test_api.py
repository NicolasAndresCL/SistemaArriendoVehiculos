"""Tests de contratos transversales de la API.

Solo cubre lo que NO depende del detalle de cada vista o serializer
(autenticación por defecto y la sonda de vida): quien termine `views.py` y
`serializers.py` añade después los tests propios de cada endpoint. Este
archivo no debe importar `apps.*.serializers` ni `apps.*.views`.
"""

import pytest


@pytest.mark.django_db
def test_reservas_rechaza_a_un_cliente_anonimo(cliente_api_anonimo):
    respuesta = cliente_api_anonimo.get("/api/v1/reservas/")
    assert respuesta.status_code == 401


@pytest.mark.django_db
def test_healthz_responde_ok_sin_autenticacion(cliente_api_anonimo):
    respuesta = cliente_api_anonimo.get("/healthz/")
    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == "ok"
