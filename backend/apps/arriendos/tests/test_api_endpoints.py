"""Tests de los endpoints de reservas, pagos y devoluciones.

Comprueban el recorrido completo por HTTP y, sobre todo, que las reglas de
negocio siguen vigentes cuando se entra por la API: que el estado no se pueda
forzar desde el cuerpo de la petición y que nadie vea ni toque lo ajeno.
"""

import datetime as dt

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.arriendos.models import Devolucion, Pago, Reserva
from apps.vehiculos.models import Vehiculo
from conftest import HOY

RESERVAS = "/api/v1/reservas/"
PAGOS = "/api/v1/pagos/"
DEVOLUCIONES = "/api/v1/devoluciones/"


def _autenticar(usuario) -> APIClient:
    token, _ = Token.objects.get_or_create(user=usuario)
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return cliente


@pytest.fixture
def cliente_api_de_cliente(db, usuario_cliente):
    return _autenticar(usuario_cliente)


@pytest.fixture
def otro_cliente_api(db, usuario_sin_licencia):
    return _autenticar(usuario_sin_licencia)


# --- Creación de reservas -------------------------------------------------


@pytest.mark.django_db
def test_crear_reserva_calcula_monto_y_deja_pendiente(cliente_api, usuario_cliente, vehiculo):
    respuesta = cliente_api.post(
        RESERVAS,
        {
            "usuario": usuario_cliente.pk,
            "vehiculo": vehiculo.pk,
            "fecha_inicio": str(HOY),
            "fecha_fin": str(HOY + dt.timedelta(days=4)),
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["estado"] == Reserva.Estado.PENDIENTE
    assert respuesta.data["dias"] == 4
    assert respuesta.data["monto_estimado"] == "80000"
    assert respuesta.data["pagada"] is False
    assert respuesta.data["tiene_devolucion"] is False


@pytest.mark.django_db
def test_el_estado_enviado_en_el_cuerpo_se_ignora(cliente_api, usuario_cliente, vehiculo):
    """`estado` es de solo lectura: si no, cualquiera confirmaría sin pagar."""
    respuesta = cliente_api.post(
        RESERVAS,
        {
            "usuario": usuario_cliente.pk,
            "vehiculo": vehiculo.pk,
            "fecha_inicio": str(HOY),
            "fecha_fin": str(HOY + dt.timedelta(days=2)),
            "estado": Reserva.Estado.CONFIRMADA,
            "monto_estimado": 1,
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["estado"] == Reserva.Estado.PENDIENTE
    assert respuesta.data["monto_estimado"] == "40000"


@pytest.mark.django_db
def test_crear_reserva_con_fechas_invalidas_devuelve_400(cliente_api, usuario_cliente, vehiculo):
    respuesta = cliente_api.post(
        RESERVAS,
        {
            "usuario": usuario_cliente.pk,
            "vehiculo": vehiculo.pk,
            "fecha_inicio": str(HOY + dt.timedelta(days=5)),
            "fecha_fin": str(HOY),
        },
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.data["error"]["codigo"] == "fechas_invalidas"


@pytest.mark.django_db
def test_crear_reserva_sobre_vehiculo_en_mantenimiento_devuelve_409(
    cliente_api, usuario_cliente, vehiculo_en_mantenimiento
):
    respuesta = cliente_api.post(
        RESERVAS,
        {
            "usuario": usuario_cliente.pk,
            "vehiculo": vehiculo_en_mantenimiento.pk,
            "fecha_inicio": str(HOY),
            "fecha_fin": str(HOY + dt.timedelta(days=2)),
        },
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["codigo"] == "vehiculo_no_disponible"
    assert respuesta.data["error"]["detalle"]["patente"] == vehiculo_en_mantenimiento.patente


@pytest.mark.django_db
def test_crear_reserva_traslapada_devuelve_409(
    cliente_api, usuario_cliente, vehiculo, reserva_pendiente
):
    respuesta = cliente_api.post(
        RESERVAS,
        {
            "usuario": usuario_cliente.pk,
            "vehiculo": vehiculo.pk,
            "fecha_inicio": str(HOY + dt.timedelta(days=1)),
            "fecha_fin": str(HOY + dt.timedelta(days=5)),
        },
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["codigo"] == "vehiculo_no_disponible"


@pytest.mark.django_db
def test_crear_reserva_con_licencia_vencida_devuelve_409(
    cliente_api, usuario_licencia_vencida, vehiculo
):
    respuesta = cliente_api.post(
        RESERVAS,
        {
            "usuario": usuario_licencia_vencida.pk,
            "vehiculo": vehiculo.pk,
            "fecha_inicio": str(HOY),
            "fecha_fin": str(HOY + dt.timedelta(days=2)),
        },
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["codigo"] == "licencia_vencida"


@pytest.mark.django_db
def test_un_cliente_reserva_siempre_a_su_nombre(
    cliente_api_de_cliente, usuario_cliente, operador, vehiculo
):
    """Mandar `usuario` ajeno en el cuerpo no permite reservar a nombre de otro."""
    respuesta = cliente_api_de_cliente.post(
        RESERVAS,
        {
            "usuario": operador.pk,
            "vehiculo": vehiculo.pk,
            "fecha_inicio": str(HOY),
            "fecha_fin": str(HOY + dt.timedelta(days=2)),
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert Reserva.objects.get(pk=respuesta.data["id"]).usuario == usuario_cliente


# --- Transiciones ---------------------------------------------------------


@pytest.mark.django_db
def test_retirar_deja_la_reserva_en_curso_y_el_vehiculo_arrendado(
    cliente_api, reserva_confirmada, vehiculo
):
    respuesta = cliente_api.post(f"{RESERVAS}{reserva_confirmada.pk}/retirar/")

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == Reserva.Estado.EN_CURSO
    vehiculo.refresh_from_db()
    assert vehiculo.estado == Vehiculo.Estado.ARRENDADO


@pytest.mark.django_db
def test_retirar_una_reserva_sin_pagar_devuelve_409(cliente_api, reserva_pendiente):
    respuesta = cliente_api.post(f"{RESERVAS}{reserva_pendiente.pk}/retirar/")

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["codigo"] == "transicion_no_permitida"
    assert respuesta.data["error"]["detalle"]["estado_actual"] == Reserva.Estado.PENDIENTE


@pytest.mark.django_db
def test_cancelar_guarda_el_motivo(cliente_api, reserva_pendiente):
    respuesta = cliente_api.post(
        f"{RESERVAS}{reserva_pendiente.pk}/cancelar/",
        {"motivo": "El cliente desistió."},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == Reserva.Estado.CANCELADA
    reserva_pendiente.refresh_from_db()
    assert "El cliente desistió." in reserva_pendiente.observaciones


@pytest.mark.django_db
def test_cancelar_sin_motivo_tambien_funciona(cliente_api, reserva_pendiente):
    respuesta = cliente_api.post(f"{RESERVAS}{reserva_pendiente.pk}/cancelar/", {}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == Reserva.Estado.CANCELADA


@pytest.mark.django_db
def test_cancelar_dos_veces_devuelve_409(cliente_api, reserva_pendiente):
    cliente_api.post(f"{RESERVAS}{reserva_pendiente.pk}/cancelar/", {}, format="json")
    respuesta = cliente_api.post(f"{RESERVAS}{reserva_pendiente.pk}/cancelar/", {}, format="json")

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["codigo"] == "transicion_no_permitida"


# --- Pagos ----------------------------------------------------------------


@pytest.mark.django_db
def test_pagar_confirma_la_reserva(cliente_api, reserva_pendiente):
    respuesta = cliente_api.post(
        PAGOS,
        {
            "reserva": reserva_pendiente.pk,
            "monto": 60000,
            "medio": Pago.Medio.DEBITO,
            "comprobante": "TRX-1",
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["estado"] == Pago.Estado.PAGADO
    assert respuesta.data["medio_display"] == "Tarjeta de débito"
    reserva_pendiente.refresh_from_db()
    assert reserva_pendiente.estado == Reserva.Estado.CONFIRMADA


@pytest.mark.django_db
def test_pagar_dos_veces_devuelve_409(cliente_api, reserva_pendiente):
    datos = {"reserva": reserva_pendiente.pk, "monto": 60000, "medio": Pago.Medio.EFECTIVO}
    assert cliente_api.post(PAGOS, datos, format="json").status_code == 201

    respuesta = cliente_api.post(PAGOS, datos, format="json")

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["codigo"] == "reserva_no_pagable"


@pytest.mark.django_db
def test_un_pago_no_se_puede_borrar(cliente_api, reserva_pendiente):
    creado = cliente_api.post(
        PAGOS,
        {"reserva": reserva_pendiente.pk, "monto": 60000, "medio": Pago.Medio.EFECTIVO},
        format="json",
    )

    respuesta = cliente_api.delete(f"{PAGOS}{creado.data['id']}/")

    assert respuesta.status_code == 405
    assert Pago.objects.filter(pk=creado.data["id"]).exists()


@pytest.mark.django_db
def test_filtro_de_pagos_por_reserva(cliente_api, reserva_pendiente):
    cliente_api.post(
        PAGOS,
        {"reserva": reserva_pendiente.pk, "monto": 60000, "medio": Pago.Medio.EFECTIVO},
        format="json",
    )

    assert cliente_api.get(f"{PAGOS}?reserva={reserva_pendiente.pk}").data["count"] == 1
    assert cliente_api.get(f"{PAGOS}?reserva=9999").data["count"] == 0


# --- Devoluciones ---------------------------------------------------------


@pytest.mark.django_db
def test_devolucion_cierra_el_arriendo_y_libera_el_vehiculo(
    cliente_api, reserva_confirmada, vehiculo
):
    respuesta = cliente_api.post(
        DEVOLUCIONES,
        {
            "reserva": reserva_confirmada.pk,
            "fecha_devolucion": str(reserva_confirmada.fecha_fin),
            "kilometraje_final": vehiculo.kilometraje + 500,
            "nivel_combustible": Devolucion.NivelCombustible.LLENO,
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["dias_atraso"] == 0
    assert respuesta.data["cargo_adicional"] == "0"
    assert respuesta.data["kilometros_recorridos"] == 500
    assert respuesta.data["nivel_combustible_display"] == "Lleno"

    reserva_confirmada.refresh_from_db()
    vehiculo.refresh_from_db()
    assert reserva_confirmada.estado == Reserva.Estado.FINALIZADA
    assert vehiculo.estado == Vehiculo.Estado.DISPONIBLE
    assert vehiculo.kilometraje == 500


@pytest.mark.django_db
def test_devolucion_con_atraso_cobra_recargo(cliente_api, reserva_confirmada, vehiculo):
    respuesta = cliente_api.post(
        DEVOLUCIONES,
        {
            "reserva": reserva_confirmada.pk,
            "fecha_devolucion": str(reserva_confirmada.fecha_fin + dt.timedelta(days=2)),
            "kilometraje_final": 100,
            "nivel_combustible": Devolucion.NivelCombustible.MEDIO,
            "cargo_por_danos": 5000,
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["dias_atraso"] == 2
    # 2 días × 20.000 × 1,5 = 60.000, más 5.000 de daños.
    assert respuesta.data["cargo_adicional"] == "65000"


@pytest.mark.django_db
def test_devolucion_con_danos_manda_el_vehiculo_a_mantenimiento(
    cliente_api, reserva_confirmada, vehiculo
):
    cliente_api.post(
        DEVOLUCIONES,
        {
            "reserva": reserva_confirmada.pk,
            "fecha_devolucion": str(reserva_confirmada.fecha_fin),
            "kilometraje_final": 300,
            "nivel_combustible": Devolucion.NivelCombustible.MEDIO,
            "danos": "Rayón en la puerta trasera derecha.",
        },
        format="json",
    )

    vehiculo.refresh_from_db()
    assert vehiculo.estado == Vehiculo.Estado.MANTENIMIENTO


@pytest.mark.django_db
def test_devolucion_con_kilometraje_menor_devuelve_400(cliente_api, reserva_confirmada, vehiculo):
    vehiculo.kilometraje = 1000
    vehiculo.save(update_fields=["kilometraje"])

    respuesta = cliente_api.post(
        DEVOLUCIONES,
        {
            "reserva": reserva_confirmada.pk,
            "fecha_devolucion": str(reserva_confirmada.fecha_fin),
            "kilometraje_final": 900,
            "nivel_combustible": Devolucion.NivelCombustible.LLENO,
        },
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.data["error"]["codigo"] == "kilometraje_invalido"
    assert respuesta.data["error"]["detalle"]["kilometraje_actual"] == 1000


@pytest.mark.django_db
def test_devolver_una_reserva_pendiente_devuelve_409(cliente_api, reserva_pendiente):
    respuesta = cliente_api.post(
        DEVOLUCIONES,
        {
            "reserva": reserva_pendiente.pk,
            "fecha_devolucion": str(HOY),
            "kilometraje_final": 100,
            "nivel_combustible": Devolucion.NivelCombustible.LLENO,
        },
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["codigo"] == "devolucion_no_permitida"


@pytest.mark.django_db
def test_un_cliente_no_puede_registrar_devoluciones(cliente_api_de_cliente, reserva_confirmada):
    """Es una operación de mostrador: cambia el estado de la flota."""
    respuesta = cliente_api_de_cliente.post(
        DEVOLUCIONES,
        {
            "reserva": reserva_confirmada.pk,
            "fecha_devolucion": str(reserva_confirmada.fecha_fin),
            "kilometraje_final": 100,
            "nivel_combustible": Devolucion.NivelCombustible.LLENO,
        },
        format="json",
    )

    assert respuesta.status_code == 403
    assert not Devolucion.objects.exists()


# --- Aislamiento entre clientes -------------------------------------------


@pytest.mark.django_db
def test_un_cliente_no_ve_las_reservas_ajenas(otro_cliente_api, reserva_pendiente):
    """El filtro de listado es la mitad que se olvida: sin él, se filtra todo."""
    respuesta = otro_cliente_api.get(RESERVAS)

    assert respuesta.status_code == 200
    assert respuesta.data["count"] == 0


@pytest.mark.django_db
def test_un_cliente_no_accede_a_una_reserva_ajena_por_id(otro_cliente_api, reserva_pendiente):
    respuesta = otro_cliente_api.get(f"{RESERVAS}{reserva_pendiente.pk}/")

    assert respuesta.status_code == 404


@pytest.mark.django_db
def test_un_cliente_no_ve_los_pagos_ajenos(otro_cliente_api, cliente_api, reserva_pendiente):
    cliente_api.post(
        PAGOS,
        {"reserva": reserva_pendiente.pk, "monto": 60000, "medio": Pago.Medio.EFECTIVO},
        format="json",
    )

    assert otro_cliente_api.get(PAGOS).data["count"] == 0
    assert cliente_api.get(PAGOS).data["count"] == 1


@pytest.mark.django_db
def test_el_dueno_si_ve_su_propia_reserva(cliente_api_de_cliente, reserva_pendiente):
    respuesta = cliente_api_de_cliente.get(RESERVAS)

    assert respuesta.data["count"] == 1
    assert respuesta.data["results"][0]["id"] == reserva_pendiente.pk


@pytest.mark.django_db
def test_filtros_de_reservas_por_estado_y_vehiculo(cliente_api, reserva_pendiente, vehiculo):
    assert cliente_api.get(f"{RESERVAS}?estado={Reserva.Estado.PENDIENTE}").data["count"] == 1
    assert cliente_api.get(f"{RESERVAS}?estado={Reserva.Estado.FINALIZADA}").data["count"] == 0
    assert cliente_api.get(f"{RESERVAS}?vehiculo={vehiculo.pk}").data["count"] == 1
    assert cliente_api.get(f"{RESERVAS}?vehiculo=9999").data["count"] == 0
