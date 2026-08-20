"""Vistas del agregado de arriendo: reservas, pagos y devoluciones."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.api.permissions import EsDuenoUOperador, EsOperadorOSoloLectura, PorDuenoMixin

from . import services
from .models import Devolucion, Pago, Reserva
from .serializers import (
    CancelacionSerializer,
    DevolucionSerializer,
    PagoSerializer,
    ReservaSerializer,
)


class ReservaViewSet(PorDuenoMixin, viewsets.ModelViewSet):
    """CRUD de reservas más las transiciones de su máquina de estados.

    Las transiciones son acciones POST explícitas y no una actualización del
    campo `estado`: cada una tiene sus propias reglas y efectos sobre el
    vehículo, y un PATCH no podría validarlas.
    """

    serializer_class = ReservaSerializer
    queryset = Reserva.objects.select_related("usuario", "vehiculo")
    permission_classes = [IsAuthenticated, EsDuenoUOperador]
    campo_dueno = "usuario"

    def get_queryset(self):
        queryset = super().get_queryset()
        if estado := self.request.query_params.get("estado"):
            queryset = queryset.filter(estado=estado)
        if vehiculo := self.request.query_params.get("vehiculo"):
            queryset = queryset.filter(vehiculo_id=vehiculo)
        return queryset

    def perform_create(self, serializer) -> None:
        # Un cliente solo reserva a su propio nombre. Sin esto, mandar
        # {"usuario": 7} en el cuerpo permitiría reservar a nombre de otro.
        if not self.request.user.is_staff:
            serializer.save(usuario=self.request.user)
        else:
            serializer.save()

    @action(detail=True, methods=["post"])
    def retirar(self, request: Request, pk: str | None = None) -> Response:
        """El cliente retira el vehículo: la reserva pasa a EN_CURSO."""
        reserva = services.registrar_retiro(reserva=self.get_object())
        return Response(self.get_serializer(reserva).data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request: Request, pk: str | None = None) -> Response:
        """Anula la reserva y devuelve el vehículo a la flota si ya había salido."""
        entrada = CancelacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        reserva = services.cancelar_reserva(
            reserva=self.get_object(), motivo=entrada.validated_data["motivo"]
        )
        return Response(self.get_serializer(reserva).data)


class PagoViewSet(PorDuenoMixin, viewsets.ModelViewSet):
    """Registro de pagos.

    Sin `destroy`: un pago no se borra, se anula. Borrarlo dejaría una reserva
    confirmada sin respaldo de cobro.
    """

    serializer_class = PagoSerializer
    queryset = Pago.objects.select_related("reserva__usuario", "reserva__vehiculo")
    permission_classes = [IsAuthenticated, EsDuenoUOperador]
    campo_dueno = "reserva__usuario"
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if reserva := self.request.query_params.get("reserva"):
            queryset = queryset.filter(reserva_id=reserva)
        return queryset


class DevolucionViewSet(PorDuenoMixin, viewsets.ModelViewSet):
    """Registro de devoluciones.

    Solo lectura y creación: una devolución es un hecho consumado del que
    depende el kilometraje y el estado del vehículo.
    """

    serializer_class = DevolucionSerializer
    queryset = Devolucion.objects.select_related("reserva__usuario", "reserva__vehiculo")
    permission_classes = [IsAuthenticated, EsDuenoUOperador]
    campo_dueno = "reserva__usuario"
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        # Registrar una devolución implica cambiar el estado de la flota:
        # es una operación de mostrador, no del cliente.
        if self.action == "create":
            return [IsAuthenticated(), EsOperadorOSoloLectura()]
        return super().get_permissions()
