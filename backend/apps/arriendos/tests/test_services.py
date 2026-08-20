"""Tests de las reglas de negocio en `apps/arriendos/services.py`.

Cada regla se cubre en sus dos sentidos: que acepte lo válido y que rechace lo
inválido con la excepción de dominio correspondiente. El objetivo es cobertura
del 100% de `services.py`, porque es el módulo que concentra toda la lógica
que antes viviría (mal) repartida en las vistas.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.arriendos.models import Devolucion, Pago, Reserva
from apps.arriendos.services import (
    calcular_cargo_adicional,
    calcular_dias,
    calcular_monto,
    cancelar_reserva,
    crear_reserva,
    hay_traslape,
    registrar_devolucion,
    registrar_pago,
    registrar_retiro,
)
from apps.vehiculos.models import Vehiculo
from core.exceptions import (
    DevolucionNoPermitidaError,
    FechasInvalidasError,
    KilometrajeInvalidoError,
    LicenciaVencidaError,
    PagoDuplicadoError,
    ReservaNoPagableError,
    TransicionNoPermitidaError,
    VehiculoNoDisponibleError,
)

# ---------------------------------------------------------------------------
# calcular_dias / calcular_monto
# ---------------------------------------------------------------------------


def test_calcular_dias_caso_normal():
    dias = calcular_dias(date(2026, 3, 1), date(2026, 3, 6))
    assert dias == 5


def test_calcular_dias_dentro_del_mismo_dia_cobra_un_dia_como_minimo():
    dias = calcular_dias(date(2026, 3, 1), date(2026, 3, 1))
    assert dias == 1


def test_calcular_monto_multiplica_dias_por_tarifa_diaria():
    vehiculo = Vehiculo(
        patente="ZZ0000",
        marca="Marca",
        modelo="Modelo",
        anio=2024,
        categoria=Vehiculo.Categoria.SEDAN,
        tarifa_diaria=Decimal("15000"),
    )
    monto = calcular_monto(vehiculo, date(2026, 3, 1), date(2026, 3, 4))
    assert monto == Decimal("45000")


# ---------------------------------------------------------------------------
# crear_reserva
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_crear_reserva_exito(usuario_cliente, vehiculo):
    reserva = crear_reserva(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 1),
        fecha_fin=date(2026, 3, 5),
    )
    assert reserva.pk is not None
    assert reserva.estado == Reserva.Estado.PENDIENTE
    assert reserva.monto_estimado == Decimal("80000")


@pytest.mark.django_db
def test_crear_reserva_rechaza_fecha_fin_anterior_o_igual_a_inicio(usuario_cliente, vehiculo):
    with pytest.raises(FechasInvalidasError):
        crear_reserva(
            usuario=usuario_cliente,
            vehiculo=vehiculo,
            fecha_inicio=date(2026, 3, 5),
            fecha_fin=date(2026, 3, 5),
        )


@pytest.mark.django_db
def test_crear_reserva_rechaza_vehiculo_en_mantenimiento(
    usuario_cliente, vehiculo_en_mantenimiento
):
    with pytest.raises(VehiculoNoDisponibleError):
        crear_reserva(
            usuario=usuario_cliente,
            vehiculo=vehiculo_en_mantenimiento,
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 5),
        )


@pytest.mark.django_db
def test_crear_reserva_rechaza_traslape_con_otra_reserva_activa(usuario_cliente, vehiculo):
    Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 1),
        fecha_fin=date(2026, 3, 10),
        estado=Reserva.Estado.CONFIRMADA,
    )
    with pytest.raises(VehiculoNoDisponibleError):
        crear_reserva(
            usuario=usuario_cliente,
            vehiculo=vehiculo,
            fecha_inicio=date(2026, 3, 5),
            fecha_fin=date(2026, 3, 8),
        )


@pytest.mark.django_db
def test_crear_reserva_no_traslapa_con_reserva_cancelada(usuario_cliente, vehiculo):
    Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 1),
        fecha_fin=date(2026, 3, 10),
        estado=Reserva.Estado.CANCELADA,
    )
    reserva = crear_reserva(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 5),
        fecha_fin=date(2026, 3, 8),
    )
    assert reserva.pk is not None


@pytest.mark.django_db
def test_crear_reserva_no_traslapa_con_reserva_finalizada(usuario_cliente, vehiculo):
    Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 1),
        fecha_fin=date(2026, 3, 10),
        estado=Reserva.Estado.FINALIZADA,
    )
    reserva = crear_reserva(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 5),
        fecha_fin=date(2026, 3, 8),
    )
    assert reserva.pk is not None


@pytest.mark.django_db
def test_crear_reserva_rechaza_licencia_vencida(usuario_licencia_vencida, vehiculo):
    with pytest.raises(LicenciaVencidaError):
        crear_reserva(
            usuario=usuario_licencia_vencida,
            vehiculo=vehiculo,
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 5),
        )


@pytest.mark.django_db
def test_crear_reserva_rechaza_licencia_nula(usuario_sin_licencia, vehiculo):
    with pytest.raises(LicenciaVencidaError):
        crear_reserva(
            usuario=usuario_sin_licencia,
            vehiculo=vehiculo,
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 5),
        )


# ---------------------------------------------------------------------------
# hay_traslape — los cuatro casos de borde
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_hay_traslape_cuando_la_nueva_empieza_antes_y_termina_dentro(usuario_cliente, vehiculo):
    Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 10),
        fecha_fin=date(2026, 3, 20),
        estado=Reserva.Estado.CONFIRMADA,
    )
    assert hay_traslape(vehiculo, date(2026, 3, 5), date(2026, 3, 15)) is True


@pytest.mark.django_db
def test_hay_traslape_cuando_la_nueva_contiene_por_completo_a_la_existente(
    usuario_cliente, vehiculo
):
    Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 10),
        fecha_fin=date(2026, 3, 20),
        estado=Reserva.Estado.CONFIRMADA,
    )
    assert hay_traslape(vehiculo, date(2026, 3, 5), date(2026, 3, 25)) is True


@pytest.mark.django_db
def test_hay_traslape_cuando_la_nueva_queda_contenida_en_la_existente(usuario_cliente, vehiculo):
    Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 10),
        fecha_fin=date(2026, 3, 20),
        estado=Reserva.Estado.CONFIRMADA,
    )
    assert hay_traslape(vehiculo, date(2026, 3, 12), date(2026, 3, 18)) is True


@pytest.mark.django_db
def test_hay_traslape_es_falso_cuando_la_nueva_empieza_justo_cuando_termina_la_otra(
    usuario_cliente, vehiculo
):
    Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 10),
        fecha_fin=date(2026, 3, 20),
        estado=Reserva.Estado.CONFIRMADA,
    )
    assert hay_traslape(vehiculo, date(2026, 3, 20), date(2026, 3, 25)) is False


# ---------------------------------------------------------------------------
# registrar_pago
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_registrar_pago_exito_deja_la_reserva_confirmada(reserva_pendiente):
    pago = registrar_pago(
        reserva=reserva_pendiente,
        monto=reserva_pendiente.monto_estimado,
        medio=Pago.Medio.EFECTIVO,
        comprobante="TRX-1",
    )
    reserva_pendiente.refresh_from_db()
    assert pago.pk is not None
    assert pago.estado == Pago.Estado.PAGADO
    assert reserva_pendiente.estado == Reserva.Estado.CONFIRMADA


@pytest.mark.django_db
def test_registrar_pago_rechaza_reserva_que_no_esta_pendiente(reserva_confirmada):
    with pytest.raises(ReservaNoPagableError):
        registrar_pago(
            reserva=reserva_confirmada,
            monto=reserva_confirmada.monto_estimado,
            medio=Pago.Medio.EFECTIVO,
        )


@pytest.mark.django_db
def test_registrar_pago_rechaza_pago_duplicado(reserva_pendiente):
    Pago.objects.create(
        reserva=reserva_pendiente,
        monto=reserva_pendiente.monto_estimado,
        medio=Pago.Medio.EFECTIVO,
        estado=Pago.Estado.PAGADO,
    )
    with pytest.raises(PagoDuplicadoError):
        registrar_pago(
            reserva=reserva_pendiente,
            monto=reserva_pendiente.monto_estimado,
            medio=Pago.Medio.CREDITO,
        )


# ---------------------------------------------------------------------------
# registrar_retiro
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_registrar_retiro_exito_deja_en_curso_y_vehiculo_arrendado(reserva_confirmada, vehiculo):
    registrar_retiro(reserva=reserva_confirmada)
    reserva_confirmada.refresh_from_db()
    vehiculo.refresh_from_db()
    assert reserva_confirmada.estado == Reserva.Estado.EN_CURSO
    assert vehiculo.estado == Vehiculo.Estado.ARRENDADO


@pytest.mark.django_db
def test_registrar_retiro_rechaza_desde_pendiente(reserva_pendiente):
    with pytest.raises(TransicionNoPermitidaError):
        registrar_retiro(reserva=reserva_pendiente)


# ---------------------------------------------------------------------------
# cancelar_reserva
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cancelar_reserva_exito_desde_pendiente(reserva_pendiente):
    cancelar_reserva(reserva=reserva_pendiente)
    reserva_pendiente.refresh_from_db()
    assert reserva_pendiente.estado == Reserva.Estado.CANCELADA


@pytest.mark.django_db
def test_cancelar_reserva_exito_desde_confirmada(reserva_confirmada):
    cancelar_reserva(reserva=reserva_confirmada)
    reserva_confirmada.refresh_from_db()
    assert reserva_confirmada.estado == Reserva.Estado.CANCELADA


@pytest.mark.django_db
def test_cancelar_reserva_desde_en_curso_devuelve_el_vehiculo_a_disponible(
    usuario_cliente, vehiculo
):
    vehiculo.estado = Vehiculo.Estado.ARRENDADO
    vehiculo.save(update_fields=["estado"])
    reserva = Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 1),
        fecha_fin=date(2026, 3, 5),
        estado=Reserva.Estado.EN_CURSO,
    )
    cancelar_reserva(reserva=reserva)
    reserva.refresh_from_db()
    vehiculo.refresh_from_db()
    assert reserva.estado == Reserva.Estado.CANCELADA
    assert vehiculo.estado == Vehiculo.Estado.DISPONIBLE


@pytest.mark.django_db
def test_cancelar_reserva_rechaza_desde_finalizada(usuario_cliente, vehiculo):
    reserva = Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 1),
        fecha_fin=date(2026, 3, 5),
        estado=Reserva.Estado.FINALIZADA,
    )
    with pytest.raises(TransicionNoPermitidaError):
        cancelar_reserva(reserva=reserva)


@pytest.mark.django_db
def test_cancelar_reserva_rechaza_desde_cancelada(usuario_cliente, vehiculo):
    reserva = Reserva.objects.create(
        usuario=usuario_cliente,
        vehiculo=vehiculo,
        fecha_inicio=date(2026, 3, 1),
        fecha_fin=date(2026, 3, 5),
        estado=Reserva.Estado.CANCELADA,
    )
    with pytest.raises(TransicionNoPermitidaError):
        cancelar_reserva(reserva=reserva)


@pytest.mark.django_db
def test_cancelar_reserva_deja_el_motivo_en_observaciones(reserva_pendiente):
    cancelar_reserva(reserva=reserva_pendiente, motivo="El cliente desistió")
    reserva_pendiente.refresh_from_db()
    assert "El cliente desistió" in reserva_pendiente.observaciones


# ---------------------------------------------------------------------------
# calcular_cargo_adicional
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_calcular_cargo_adicional_sin_atraso_ni_danos_es_cero(reserva_confirmada):
    dias_atraso, cargo = calcular_cargo_adicional(
        reserva=reserva_confirmada,
        fecha_devolucion=reserva_confirmada.fecha_fin,
        cargo_por_danos=Decimal("0"),
    )
    assert dias_atraso == 0
    assert cargo == Decimal("0")


@pytest.mark.django_db
def test_calcular_cargo_adicional_con_atraso_aplica_factor_1_5(reserva_confirmada):
    fecha_devolucion = reserva_confirmada.fecha_fin + timedelta(days=2)
    dias_atraso, cargo = calcular_cargo_adicional(
        reserva=reserva_confirmada,
        fecha_devolucion=fecha_devolucion,
        cargo_por_danos=Decimal("0"),
    )
    tarifa = reserva_confirmada.vehiculo.tarifa_diaria
    assert dias_atraso == 2
    assert cargo == (Decimal(2) * tarifa * Decimal("1.5")).quantize(Decimal("1"))


@pytest.mark.django_db
def test_calcular_cargo_adicional_suma_el_cargo_por_danos(reserva_confirmada):
    _, cargo = calcular_cargo_adicional(
        reserva=reserva_confirmada,
        fecha_devolucion=reserva_confirmada.fecha_fin,
        cargo_por_danos=Decimal("15000"),
    )
    assert cargo == Decimal("15000")


# ---------------------------------------------------------------------------
# registrar_devolucion
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_registrar_devolucion_exito_finaliza_reserva_y_libera_vehiculo(
    reserva_confirmada, vehiculo
):
    devolucion = registrar_devolucion(
        reserva=reserva_confirmada,
        fecha_devolucion=reserva_confirmada.fecha_fin,
        kilometraje_final=500,
        nivel_combustible=Devolucion.NivelCombustible.LLENO,
    )
    reserva_confirmada.refresh_from_db()
    vehiculo.refresh_from_db()
    assert devolucion.pk is not None
    assert reserva_confirmada.estado == Reserva.Estado.FINALIZADA
    assert vehiculo.estado == Vehiculo.Estado.DISPONIBLE
    assert vehiculo.kilometraje == 500


@pytest.mark.django_db
def test_registrar_devolucion_con_danos_deja_el_vehiculo_en_mantenimiento(
    reserva_confirmada, vehiculo
):
    registrar_devolucion(
        reserva=reserva_confirmada,
        fecha_devolucion=reserva_confirmada.fecha_fin,
        kilometraje_final=500,
        nivel_combustible=Devolucion.NivelCombustible.MEDIO,
        danos="Rayón en la puerta trasera.",
    )
    vehiculo.refresh_from_db()
    assert vehiculo.estado == Vehiculo.Estado.MANTENIMIENTO


@pytest.mark.django_db
def test_registrar_devolucion_con_dejar_en_mantenimiento_deja_el_vehiculo_en_mantenimiento(
    reserva_confirmada, vehiculo
):
    registrar_devolucion(
        reserva=reserva_confirmada,
        fecha_devolucion=reserva_confirmada.fecha_fin,
        kilometraje_final=500,
        nivel_combustible=Devolucion.NivelCombustible.LLENO,
        dejar_en_mantenimiento=True,
    )
    vehiculo.refresh_from_db()
    assert vehiculo.estado == Vehiculo.Estado.MANTENIMIENTO


@pytest.mark.django_db
def test_registrar_devolucion_rechaza_desde_pendiente(reserva_pendiente):
    with pytest.raises(DevolucionNoPermitidaError):
        registrar_devolucion(
            reserva=reserva_pendiente,
            fecha_devolucion=reserva_pendiente.fecha_fin,
            kilometraje_final=100,
            nivel_combustible=Devolucion.NivelCombustible.LLENO,
        )


@pytest.mark.django_db
def test_registrar_devolucion_rechaza_devolver_dos_veces(reserva_confirmada):
    registrar_devolucion(
        reserva=reserva_confirmada,
        fecha_devolucion=reserva_confirmada.fecha_fin,
        kilometraje_final=100,
        nivel_combustible=Devolucion.NivelCombustible.LLENO,
    )
    # Forzamos la reserva de vuelta a CONFIRMADA para aislar la validación de
    # "ya fue devuelta" (hasattr) de la validación de estado de la reserva,
    # que en el flujo normal ya la habría bloqueado antes.
    reserva_confirmada.estado = Reserva.Estado.CONFIRMADA
    reserva_confirmada.save(update_fields=["estado"])
    with pytest.raises(DevolucionNoPermitidaError):
        registrar_devolucion(
            reserva=reserva_confirmada,
            fecha_devolucion=reserva_confirmada.fecha_fin,
            kilometraje_final=200,
            nivel_combustible=Devolucion.NivelCombustible.LLENO,
        )


@pytest.mark.django_db
def test_registrar_devolucion_rechaza_kilometraje_menor_al_del_vehiculo(
    reserva_confirmada, vehiculo
):
    vehiculo.kilometraje = 1000
    vehiculo.save(update_fields=["kilometraje"])
    with pytest.raises(KilometrajeInvalidoError):
        registrar_devolucion(
            reserva=reserva_confirmada,
            fecha_devolucion=reserva_confirmada.fecha_fin,
            kilometraje_final=500,
            nivel_combustible=Devolucion.NivelCombustible.LLENO,
        )


@pytest.mark.django_db
def test_registrar_devolucion_congela_kilometraje_inicial_y_calcula_km_recorridos(
    reserva_confirmada, vehiculo
):
    vehiculo.kilometraje = 200
    vehiculo.save(update_fields=["kilometraje"])
    devolucion = registrar_devolucion(
        reserva=reserva_confirmada,
        fecha_devolucion=reserva_confirmada.fecha_fin,
        kilometraje_final=550,
        nivel_combustible=Devolucion.NivelCombustible.LLENO,
    )
    assert devolucion.kilometraje_inicial == 200
    assert devolucion.kilometraje_final == 550
    assert devolucion.kilometros_recorridos == 350
