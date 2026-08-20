"""Tests de los permisos reutilizables.

`EsDuenoUOperador` se prueba directamente y no solo a través de la API: por la
vía HTTP, el filtro de queryset ya devuelve 404 antes de que el permiso de
objeto llegue a ejecutarse, así que sin estos tests la segunda mitad de la
protección quedaría sin verificar.
"""

import pytest
from rest_framework.test import APIRequestFactory

from core.api.permissions import EsDuenoUOperador, EsOperadorOSoloLectura


class VistaFalsa:
    """Sustituto mínimo de una vista: solo aporta `campo_dueno`."""

    def __init__(self, campo_dueno: str = "usuario") -> None:
        self.campo_dueno = campo_dueno


@pytest.fixture
def peticiones():
    return APIRequestFactory()


@pytest.mark.django_db
def test_el_dueno_directo_accede_a_su_objeto(peticiones, usuario_cliente, reserva_pendiente):
    peticion = peticiones.get("/")
    peticion.user = usuario_cliente

    assert EsDuenoUOperador().has_object_permission(peticion, VistaFalsa(), reserva_pendiente)


@pytest.mark.django_db
def test_un_tercero_no_accede_al_objeto_ajeno(peticiones, usuario_sin_licencia, reserva_pendiente):
    peticion = peticiones.get("/")
    peticion.user = usuario_sin_licencia

    assert not EsDuenoUOperador().has_object_permission(peticion, VistaFalsa(), reserva_pendiente)


@pytest.mark.django_db
def test_el_operador_accede_a_cualquier_objeto(peticiones, operador, reserva_pendiente):
    peticion = peticiones.get("/")
    peticion.user = operador

    assert EsDuenoUOperador().has_object_permission(peticion, VistaFalsa(), reserva_pendiente)


@pytest.mark.django_db
def test_el_dueno_se_resuelve_a_traves_de_relaciones_anidadas(
    peticiones, usuario_cliente, reserva_pendiente
):
    """`campo_dueno` admite rutas con `__`, como en pagos y devoluciones."""
    from apps.arriendos.models import Pago

    pago = Pago.objects.create(reserva=reserva_pendiente, monto=1000, medio=Pago.Medio.EFECTIVO)
    peticion = peticiones.get("/")
    peticion.user = usuario_cliente

    vista = VistaFalsa(campo_dueno="reserva__usuario")
    assert EsDuenoUOperador().has_object_permission(peticion, vista, pago)


@pytest.mark.django_db
def test_una_ruta_de_dueno_inexistente_niega_el_acceso(
    peticiones, usuario_cliente, reserva_pendiente
):
    """Ante una ruta que no resuelve, se niega: nunca se concede por omisión."""
    peticion = peticiones.get("/")
    peticion.user = usuario_cliente

    vista = VistaFalsa(campo_dueno="campo__que__no__existe")
    assert not EsDuenoUOperador().has_object_permission(peticion, vista, reserva_pendiente)


@pytest.mark.django_db
def test_lectura_abierta_y_escritura_solo_para_funcionarios(peticiones, usuario_cliente, operador):
    permiso = EsOperadorOSoloLectura()

    lectura = peticiones.get("/")
    lectura.user = usuario_cliente
    assert permiso.has_permission(lectura, VistaFalsa())

    escritura = peticiones.post("/")
    escritura.user = usuario_cliente
    assert not permiso.has_permission(escritura, VistaFalsa())

    escritura_operador = peticiones.post("/")
    escritura_operador.user = operador
    assert permiso.has_permission(escritura_operador, VistaFalsa())
