"""Fixtures compartidas por toda la suite de tests del backend.

Vive en la raíz de `backend/` (ver `pythonpath` en `pyproject.toml`) para que
cualquier test de cualquier app la pueda pedir sin imports cruzados entre apps.
"""

import datetime as dt
from decimal import Decimal

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.arriendos.models import Reserva
from apps.usuarios.models import Usuario
from apps.vehiculos.models import Vehiculo

# Ancla fija de fechas: evita que los tests dependan del reloj real.
HOY = dt.date(2026, 1, 1)


@pytest.fixture
def usuario_cliente(db):
    """Cliente con licencia de conducir vigente."""
    return Usuario.objects.create_user(
        email="cliente@correo.cl",
        password="clave-segura",
        rut="11.111.111-1",
        nombre="Ana",
        apellido="Pérez",
        licencia_numero="L-001",
        licencia_vencimiento=HOY + dt.timedelta(days=365),
    )


@pytest.fixture
def usuario_sin_licencia(db):
    """Cliente sin ningún dato de licencia registrado."""
    return Usuario.objects.create_user(
        email="sinlicencia@correo.cl",
        password="clave-segura",
        rut="22.222.222-2",
        nombre="Beto",
        apellido="Soto",
    )


@pytest.fixture
def usuario_licencia_vencida(db):
    """Cliente cuya licencia venció antes de la fecha ancla."""
    return Usuario.objects.create_user(
        email="vencido@correo.cl",
        password="clave-segura",
        rut="33.333.333-3",
        nombre="Carla",
        apellido="Ríos",
        licencia_numero="L-002",
        licencia_vencimiento=HOY - dt.timedelta(days=1),
    )


@pytest.fixture
def operador(db):
    """Funcionario del sistema (`is_staff=True`)."""
    return Usuario.objects.create_user(
        email="operador@correo.cl",
        password="clave-segura",
        rut="44.444.444-4",
        nombre="Diego",
        apellido="Muñoz",
        is_staff=True,
    )


@pytest.fixture
def vehiculo(db):
    """Vehículo disponible para arriendo."""
    return Vehiculo.objects.create(
        patente="AABB11",
        marca="Toyota",
        modelo="Yaris",
        anio=2022,
        categoria=Vehiculo.Categoria.CITYCAR,
        tarifa_diaria=Decimal("20000"),
    )


@pytest.fixture
def vehiculo_en_mantenimiento(db):
    """Vehículo que no admite reservas nuevas."""
    return Vehiculo.objects.create(
        patente="CCDD22",
        marca="Chevrolet",
        modelo="Sail",
        anio=2020,
        categoria=Vehiculo.Categoria.SEDAN,
        tarifa_diaria=Decimal("18000"),
        estado=Vehiculo.Estado.MANTENIMIENTO,
    )


@pytest.fixture
def reserva_pendiente(db, usuario_cliente, vehiculo):
    """Reserva recién creada, sin pago registrado."""
    return Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=HOY,
        fecha_fin=HOY + dt.timedelta(days=3),
        estado=Reserva.Estado.PENDIENTE,
        monto_estimado=Decimal("60000"),
    )


@pytest.fixture
def reserva_confirmada(db, usuario_cliente, vehiculo):
    """Reserva ya pagada, lista para el retiro del vehículo."""
    return Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=HOY,
        fecha_fin=HOY + dt.timedelta(days=3),
        estado=Reserva.Estado.CONFIRMADA,
        monto_estimado=Decimal("60000"),
    )


@pytest.fixture
def cliente_api(db, operador):
    """`APIClient` autenticado con el token del operador."""
    token, _ = Token.objects.get_or_create(user=operador)
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return cliente


@pytest.fixture
def cliente_api_anonimo():
    """`APIClient` sin credenciales."""
    return APIClient()
