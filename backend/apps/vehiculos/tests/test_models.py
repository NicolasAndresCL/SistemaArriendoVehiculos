"""Tests del modelo `Vehiculo`."""

from decimal import Decimal

import pytest

from apps.vehiculos.models import Vehiculo


def _vehiculo(**overrides) -> Vehiculo:
    datos = {
        "patente": "ABCD12",
        "marca": "Nissan",
        "modelo": "Versa",
        "anio": 2023,
        "categoria": Vehiculo.Categoria.SEDAN,
        "tarifa_diaria": Decimal("22000"),
    }
    datos.update(overrides)
    return Vehiculo(**datos)


def test_str_incluye_patente_marca_y_modelo():
    vehiculo = _vehiculo()
    assert str(vehiculo) == "ABCD12 — Nissan Versa"


def test_descripcion_incluye_marca_modelo_y_anio():
    vehiculo = _vehiculo()
    assert vehiculo.descripcion == "Nissan Versa 2023"


@pytest.mark.parametrize(
    "estado, esperado",
    [
        (Vehiculo.Estado.DISPONIBLE, True),
        (Vehiculo.Estado.ARRENDADO, False),
        (Vehiculo.Estado.MANTENIMIENTO, False),
        (Vehiculo.Estado.BAJA, False),
    ],
)
def test_arrendable_segun_estado(estado, esperado):
    vehiculo = _vehiculo(estado=estado)
    assert vehiculo.arrendable is esperado
