"""Excepciones de dominio del sistema de arriendos.

Las reglas de negocio LANZAN; no arman una `Response` a mano. Así un servicio
se puede probar con `pytest.raises(...)` sin levantar HTTP, y un único
manejador traduce la excepción al contrato de error de la API.

Cualquier excepción que no derive de `ArriendoError` es un bug: el manejador la
deja escalar a un 500 ruidoso en vez de disfrazarla de error de negocio.
"""

from rest_framework import status


class ArriendoError(Exception):
    """Raíz de los errores de negocio del sistema."""

    codigo: str = "error_arriendo"
    http_status: int = status.HTTP_400_BAD_REQUEST
    mensaje: str = "No se pudo completar la operación."

    def __init__(self, mensaje: str | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        super().__init__(self.mensaje)

    def detalle(self) -> dict:
        """Datos extra que ayudan al cliente a explicar el error."""
        return {}


class FechasInvalidasError(ArriendoError):
    codigo = "fechas_invalidas"
    http_status = status.HTTP_400_BAD_REQUEST
    mensaje = "La fecha de término debe ser posterior a la de inicio."


class VehiculoNoDisponibleError(ArriendoError):
    # 409 y no 400: la petición está bien formada, choca con el estado actual.
    # "Alguien se te adelantó", no "te equivocaste al pedir".
    codigo = "vehiculo_no_disponible"
    http_status = status.HTTP_409_CONFLICT
    mensaje = "El vehículo no está disponible en el período solicitado."

    def __init__(self, mensaje: str | None = None, patente: str | None = None) -> None:
        super().__init__(mensaje)
        self.patente = patente

    def detalle(self) -> dict:
        return {"patente": self.patente} if self.patente else {}


class LicenciaVencidaError(ArriendoError):
    codigo = "licencia_vencida"
    http_status = status.HTTP_409_CONFLICT
    mensaje = "El cliente no tiene licencia de conducir vigente para ese período."


class ReservaNoPagableError(ArriendoError):
    codigo = "reserva_no_pagable"
    http_status = status.HTTP_409_CONFLICT
    mensaje = "Solo una reserva pendiente admite el registro de un pago."

    def __init__(self, mensaje: str | None = None, estado_actual: str | None = None) -> None:
        super().__init__(mensaje)
        self.estado_actual = estado_actual

    def detalle(self) -> dict:
        return {"estado_actual": self.estado_actual} if self.estado_actual else {}


class PagoDuplicadoError(ArriendoError):
    codigo = "pago_duplicado"
    http_status = status.HTTP_409_CONFLICT
    mensaje = "La reserva ya tiene un pago registrado."


class TransicionNoPermitidaError(ArriendoError):
    codigo = "transicion_no_permitida"
    http_status = status.HTTP_409_CONFLICT
    mensaje = "La reserva no admite esa transición desde su estado actual."

    def __init__(
        self,
        mensaje: str | None = None,
        estado_actual: str | None = None,
        estado_destino: str | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.estado_actual = estado_actual
        self.estado_destino = estado_destino

    def detalle(self) -> dict:
        return {"estado_actual": self.estado_actual, "estado_destino": self.estado_destino}


class DevolucionNoPermitidaError(ArriendoError):
    codigo = "devolucion_no_permitida"
    http_status = status.HTTP_409_CONFLICT
    mensaje = "Solo una reserva confirmada o en curso admite devolución, y solo una vez."


class KilometrajeInvalidoError(ArriendoError):
    codigo = "kilometraje_invalido"
    http_status = status.HTTP_400_BAD_REQUEST
    mensaje = "El kilometraje de devolución no puede ser menor al registrado en el vehículo."

    def __init__(self, mensaje: str | None = None, kilometraje_actual: int | None = None) -> None:
        super().__init__(mensaje)
        self.kilometraje_actual = kilometraje_actual

    def detalle(self) -> dict:
        return {"kilometraje_actual": self.kilometraje_actual}
