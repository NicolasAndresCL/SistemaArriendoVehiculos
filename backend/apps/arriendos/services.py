"""Reglas de negocio del arriendo.

Todo lo que decide si una operación es legítima vive aquí, no en las vistas.
Cada función valida y LANZA una excepción de dominio si la regla no se cumple;
el manejador de la API se encarga de traducirla a HTTP. Eso permite probar las
reglas con pytest.raises(...) sin levantar un servidor.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction

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

from .models import Devolucion, Pago, Reserva

# Recargo por día de atraso en la devolución: día y medio de tarifa.
FACTOR_ATRASO = Decimal("1.5")


def calcular_dias(fecha_inicio: date, fecha_fin: date) -> int:
    """Días facturables entre dos fechas. Mínimo uno."""
    return max(1, (fecha_fin - fecha_inicio).days)


def calcular_monto(vehiculo: Vehiculo, fecha_inicio: date, fecha_fin: date) -> Decimal:
    """Monto estimado del arriendo, sin cargos posteriores."""
    return Decimal(calcular_dias(fecha_inicio, fecha_fin)) * vehiculo.tarifa_diaria


def validar_fechas(fecha_inicio: date, fecha_fin: date) -> None:
    """El período debe tener sentido: término posterior al inicio."""
    if fecha_fin <= fecha_inicio:
        raise FechasInvalidasError()


def hay_traslape(vehiculo: Vehiculo, fecha_inicio: date, fecha_fin: date, excluir_id=None) -> bool:
    """¿El vehículo ya está comprometido en alguna parte de ese período?

    Dos períodos se traslapan si cada uno empieza antes de que el otro termine.
    Solo cuentan las reservas activas: una cancelada o finalizada no bloquea.
    """
    consulta = Reserva.objects.filter(
        vehiculo=vehiculo,
        estado__in=Reserva.ESTADOS_ACTIVOS,
        fecha_inicio__lt=fecha_fin,
        fecha_fin__gt=fecha_inicio,
    )
    if excluir_id is not None:
        consulta = consulta.exclude(pk=excluir_id)
    return consulta.exists()


@transaction.atomic
def crear_reserva(
    *,
    usuario,
    vehiculo: Vehiculo,
    fecha_inicio: date,
    fecha_fin: date,
    observaciones: str = "",
) -> Reserva:
    """Compromete un vehículo para un cliente.

    Rechaza si las fechas no tienen sentido, si el vehículo no está disponible,
    si ya hay otra reserva activa que se traslapa, o si el cliente no tiene
    licencia vigente al inicio del arriendo.
    """
    validar_fechas(fecha_inicio, fecha_fin)

    if not vehiculo.arrendable:
        raise VehiculoNoDisponibleError(
            f"El vehículo {vehiculo.patente} está en estado "
            f"«{vehiculo.get_estado_display()}» y no admite reservas.",
            patente=vehiculo.patente,
        )

    if hay_traslape(vehiculo, fecha_inicio, fecha_fin):
        raise VehiculoNoDisponibleError(
            f"El vehículo {vehiculo.patente} ya tiene una reserva activa en ese período.",
            patente=vehiculo.patente,
        )

    if not usuario.licencia_vigente_al(fecha_inicio):
        raise LicenciaVencidaError(
            f"{usuario.nombre_completo} no tiene licencia de conducir vigente al "
            f"{fecha_inicio:%d-%m-%Y}."
        )

    return Reserva.objects.create(
        usuario=usuario,
        vehiculo=vehiculo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=Reserva.Estado.PENDIENTE,
        monto_estimado=calcular_monto(vehiculo, fecha_inicio, fecha_fin),
        observaciones=observaciones,
    )


@transaction.atomic
def registrar_pago(
    *,
    reserva: Reserva,
    monto: Decimal,
    medio: str,
    comprobante: str = "",
) -> Pago:
    """Cobra la reserva y la deja confirmada.

    Solo una reserva PENDIENTE admite pago, y solo uno: pagar dos veces la
    misma reserva es un error del operador, no una operación válida.
    """
    if reserva.estado != Reserva.Estado.PENDIENTE:
        raise ReservaNoPagableError(
            f"La reserva #{reserva.pk} está en estado «{reserva.get_estado_display()}».",
            estado_actual=reserva.estado,
        )

    if reserva.pagos.filter(estado=Pago.Estado.PAGADO).exists():
        raise PagoDuplicadoError(f"La reserva #{reserva.pk} ya fue pagada.")

    pago = Pago.objects.create(
        reserva=reserva,
        monto=monto,
        medio=medio,
        estado=Pago.Estado.PAGADO,
        comprobante=comprobante,
    )

    reserva.estado = Reserva.Estado.CONFIRMADA
    reserva.save(update_fields=["estado", "actualizada_en"])
    return pago


@transaction.atomic
def registrar_retiro(*, reserva: Reserva) -> Reserva:
    """El cliente retira el vehículo: la reserva pasa a EN_CURSO.

    Es el momento en que el vehículo deja de estar disponible en la flota.
    """
    if reserva.estado != Reserva.Estado.CONFIRMADA:
        raise TransicionNoPermitidaError(
            f"Solo una reserva confirmada admite el retiro; la #{reserva.pk} está en "
            f"«{reserva.get_estado_display()}».",
            estado_actual=reserva.estado,
            estado_destino=Reserva.Estado.EN_CURSO,
        )

    reserva.estado = Reserva.Estado.EN_CURSO
    reserva.save(update_fields=["estado", "actualizada_en"])

    vehiculo = reserva.vehiculo
    vehiculo.estado = Vehiculo.Estado.ARRENDADO
    vehiculo.save(update_fields=["estado"])
    return reserva


@transaction.atomic
def cancelar_reserva(*, reserva: Reserva, motivo: str = "") -> Reserva:
    """Anula una reserva que aún no se cerró.

    Una reserva ya finalizada no se cancela: reescribir el pasado ocultaría un
    arriendo que efectivamente ocurrió.
    """
    if reserva.estado in (Reserva.Estado.FINALIZADA, Reserva.Estado.CANCELADA):
        raise TransicionNoPermitidaError(
            f"La reserva #{reserva.pk} ya está en estado «{reserva.get_estado_display()}».",
            estado_actual=reserva.estado,
            estado_destino=Reserva.Estado.CANCELADA,
        )

    # Si el vehículo ya había salido, vuelve a la flota.
    if reserva.estado == Reserva.Estado.EN_CURSO:
        vehiculo = reserva.vehiculo
        vehiculo.estado = Vehiculo.Estado.DISPONIBLE
        vehiculo.save(update_fields=["estado"])

    reserva.estado = Reserva.Estado.CANCELADA
    if motivo:
        reserva.observaciones = f"{reserva.observaciones}\nCancelada: {motivo}".strip()
    reserva.save(update_fields=["estado", "observaciones", "actualizada_en"])
    return reserva


def calcular_cargo_adicional(
    *, reserva: Reserva, fecha_devolucion: date, cargo_por_danos: Decimal
) -> tuple[int, Decimal]:
    """Días de atraso y cargo total extra de una devolución.

    Devuelve la tupla (dias_atraso, cargo_adicional). El atraso se cobra a
    tarifa diaria con recargo; los daños se suman tal como los tasó el operador.
    """
    dias_atraso = max(0, (fecha_devolucion - reserva.fecha_fin).days)
    recargo = Decimal(dias_atraso) * reserva.vehiculo.tarifa_diaria * FACTOR_ATRASO
    return dias_atraso, (recargo + cargo_por_danos).quantize(Decimal("1"))


@transaction.atomic
def registrar_devolucion(
    *,
    reserva: Reserva,
    fecha_devolucion: date,
    kilometraje_final: int,
    nivel_combustible: str,
    danos: str = "",
    cargo_por_danos: Decimal = Decimal("0"),
    dejar_en_mantenimiento: bool = False,
) -> Devolucion:
    """Cierra el arriendo, libera el vehículo y calcula los cargos extra."""
    if reserva.estado not in (Reserva.Estado.CONFIRMADA, Reserva.Estado.EN_CURSO):
        raise DevolucionNoPermitidaError(
            f"La reserva #{reserva.pk} está en estado «{reserva.get_estado_display()}»."
        )

    if hasattr(reserva, "devolucion"):
        raise DevolucionNoPermitidaError(f"La reserva #{reserva.pk} ya fue devuelta.")

    vehiculo = reserva.vehiculo
    if kilometraje_final < vehiculo.kilometraje:
        # Separador de miles con punto, como se escribe en Chile.
        km_legible = f"{vehiculo.kilometraje:,}".replace(",", ".")
        raise KilometrajeInvalidoError(
            f"El vehículo {vehiculo.patente} tiene {km_legible} km registrados.",
            kilometraje_actual=vehiculo.kilometraje,
        )

    dias_atraso, cargo_adicional = calcular_cargo_adicional(
        reserva=reserva, fecha_devolucion=fecha_devolucion, cargo_por_danos=cargo_por_danos
    )

    estado_resultante = (
        Vehiculo.Estado.MANTENIMIENTO
        if (dejar_en_mantenimiento or danos.strip())
        else Vehiculo.Estado.DISPONIBLE
    )

    devolucion = Devolucion.objects.create(
        reserva=reserva,
        fecha_devolucion=fecha_devolucion,
        kilometraje_inicial=vehiculo.kilometraje,
        kilometraje_final=kilometraje_final,
        nivel_combustible=nivel_combustible,
        danos=danos,
        cargo_adicional=cargo_adicional,
        dias_atraso=dias_atraso,
        estado_vehiculo_resultante=estado_resultante,
    )

    vehiculo.kilometraje = kilometraje_final
    vehiculo.estado = estado_resultante
    vehiculo.save(update_fields=["kilometraje", "estado"])

    reserva.estado = Reserva.Estado.FINALIZADA
    reserva.save(update_fields=["estado", "actualizada_en"])
    return devolucion
