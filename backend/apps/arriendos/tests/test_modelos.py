"""Tests de los modelos de `apps/arriendos` (fuera de las reglas de negocio).

Cubre las propiedades calculadas de `Reserva` y la restricción de base de
datos que garantiza que `fecha_fin` sea posterior a `fecha_inicio` incluso si
algún código nuevo se salta `services.crear_reserva`.
"""

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from apps.arriendos.models import Reserva

# ---------------------------------------------------------------------------
# Reserva.dias
# ---------------------------------------------------------------------------


def test_dias_caso_normal():
    reserva = Reserva(fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 1, 5))
    assert reserva.dias == 4


def test_dias_dentro_del_mismo_dia_cobra_un_dia_como_minimo():
    reserva = Reserva(fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 1, 1))
    assert reserva.dias == 1


# ---------------------------------------------------------------------------
# Reserva.esta_activa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "estado, esperado",
    [
        (Reserva.Estado.PENDIENTE, True),
        (Reserva.Estado.CONFIRMADA, True),
        (Reserva.Estado.EN_CURSO, True),
        (Reserva.Estado.FINALIZADA, False),
        (Reserva.Estado.CANCELADA, False),
    ],
)
def test_esta_activa_segun_estado(estado, esperado):
    reserva = Reserva(estado=estado)
    assert reserva.esta_activa is esperado


# ---------------------------------------------------------------------------
# Restricción de base de datos: fecha_fin posterior a fecha_inicio
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fecha_inicio, fecha_fin",
    [
        (date(2026, 5, 10), date(2026, 5, 10)),  # mismo día no es "posterior"
        (date(2026, 5, 10), date(2026, 5, 5)),  # fecha_fin antes de fecha_inicio
    ],
)
def test_restriccion_fecha_fin_posterior_a_inicio_rechaza_fechas_invalidas(
    usuario_cliente, vehiculo, fecha_inicio, fecha_fin
):
    with pytest.raises(IntegrityError), transaction.atomic():
        Reserva.objects.create(
            usuario=usuario_cliente,
            vehiculo=vehiculo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
