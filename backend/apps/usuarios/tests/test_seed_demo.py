"""Tests del comando de carga de datos de demostración.

Importan porque el trabajo de arranque del CI depende de este comando: si
`seed_demo` se rompe, el pipeline falla en un punto mucho más difícil de
diagnosticar que un test.
"""

import pytest
from django.core.management import call_command

from apps.arriendos.models import Devolucion, Pago, Reserva
from apps.usuarios.management.commands.seed_demo import EMAIL_ADMIN, PASSWORD_ADMIN
from apps.usuarios.models import Usuario
from apps.vehiculos.models import Vehiculo


@pytest.mark.django_db
def test_seed_crea_el_administrador_con_la_credencial_del_enunciado():
    call_command("seed_demo", verbosity=0)

    admin = Usuario.objects.get(email=EMAIL_ADMIN)
    assert admin.is_staff and admin.is_superuser
    assert admin.check_password(PASSWORD_ADMIN)
    assert admin.rol == Usuario.Rol.OPERADOR


@pytest.mark.django_db
def test_seed_deja_datos_en_los_cinco_registros():
    call_command("seed_demo", verbosity=0)

    assert Usuario.objects.count() == 4
    assert Vehiculo.objects.count() == 8
    assert Reserva.objects.count() == 4
    assert Pago.objects.exists()
    assert Devolucion.objects.exists()


@pytest.mark.django_db
def test_seed_cubre_los_cuatro_estados_relevantes_de_reserva():
    """La demostración no puede mostrar todas las reservas en el mismo estado."""
    call_command("seed_demo", verbosity=0)

    estados = set(Reserva.objects.values_list("estado", flat=True))
    assert estados == {
        Reserva.Estado.PENDIENTE,
        Reserva.Estado.CONFIRMADA,
        Reserva.Estado.EN_CURSO,
        Reserva.Estado.FINALIZADA,
    }


@pytest.mark.django_db
def test_seed_deja_un_cliente_con_la_licencia_vencida():
    """Sin él, la regla que rechaza esa reserva no se puede demostrar."""
    call_command("seed_demo", verbosity=0)

    clientes = Usuario.objects.filter(rol=Usuario.Rol.CLIENTE)
    assert any(not c.licencia_vigente_al(c.fecha_registro.date()) for c in clientes)


@pytest.mark.django_db
def test_seed_es_idempotente():
    """Se ejecuta en cada arranque del CI: correrlo dos veces no debe duplicar."""
    call_command("seed_demo", verbosity=0)
    conteos = (Usuario.objects.count(), Vehiculo.objects.count(), Reserva.objects.count())

    call_command("seed_demo", verbosity=0)

    assert (Usuario.objects.count(), Vehiculo.objects.count(), Reserva.objects.count()) == conteos
