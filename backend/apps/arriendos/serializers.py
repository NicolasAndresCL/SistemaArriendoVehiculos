"""Serializers del agregado de arriendo.

Los serializers validan la FORMA de los datos (tipos, obligatoriedad,
existencia de las claves foráneas). Las reglas de negocio —disponibilidad,
traslapes, transiciones de estado— viven en `services.py` y se invocan desde
`create()`, de modo que la misma regla protege a la API y a cualquier otro
punto de entrada.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.usuarios.models import Usuario
from apps.vehiculos.models import Vehiculo

from . import services
from .models import Devolucion, Pago, Reserva


class ReservaSerializer(serializers.ModelSerializer):
    """Reserva, con los datos del cliente y del vehículo ya resueltos."""

    usuario = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    vehiculo = serializers.PrimaryKeyRelatedField(queryset=Vehiculo.objects.all())

    usuario_nombre = serializers.CharField(source="usuario.nombre_completo", read_only=True)
    usuario_email = serializers.EmailField(source="usuario.email", read_only=True)
    vehiculo_patente = serializers.CharField(source="vehiculo.patente", read_only=True)
    vehiculo_descripcion = serializers.CharField(source="vehiculo.descripcion", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    dias = serializers.IntegerField(read_only=True)
    pagada = serializers.SerializerMethodField()
    tiene_devolucion = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = [
            "id",
            "usuario",
            "usuario_nombre",
            "usuario_email",
            "vehiculo",
            "vehiculo_patente",
            "vehiculo_descripcion",
            "fecha_inicio",
            "fecha_fin",
            "dias",
            "estado",
            "estado_display",
            "monto_estimado",
            "observaciones",
            "pagada",
            "tiene_devolucion",
            "creada_en",
        ]
        # El estado y el monto NO se envían desde el cliente: los determina el
        # servicio. Si fueran escribibles, cualquiera podría confirmar una
        # reserva sin pagarla mandando {"estado": "CONFIRMADA"}.
        read_only_fields = ["id", "estado", "monto_estimado", "creada_en"]

    def get_pagada(self, obj: Reserva) -> bool:
        return obj.pagos.filter(estado=Pago.Estado.PAGADO).exists()

    def get_tiene_devolucion(self, obj: Reserva) -> bool:
        return hasattr(obj, "devolucion")

    def create(self, validated_data: dict) -> Reserva:
        return services.crear_reserva(
            usuario=validated_data["usuario"],
            vehiculo=validated_data["vehiculo"],
            fecha_inicio=validated_data["fecha_inicio"],
            fecha_fin=validated_data["fecha_fin"],
            observaciones=validated_data.get("observaciones", ""),
        )


class PagoSerializer(serializers.ModelSerializer):
    """Pago de una reserva."""

    reserva = serializers.PrimaryKeyRelatedField(queryset=Reserva.objects.all())
    usuario_nombre = serializers.CharField(source="reserva.usuario.nombre_completo", read_only=True)
    vehiculo_patente = serializers.CharField(source="reserva.vehiculo.patente", read_only=True)
    medio_display = serializers.CharField(source="get_medio_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id",
            "reserva",
            "usuario_nombre",
            "vehiculo_patente",
            "monto",
            "medio",
            "medio_display",
            "estado",
            "estado_display",
            "comprobante",
            "fecha_pago",
        ]
        read_only_fields = ["id", "estado", "fecha_pago"]

    def create(self, validated_data: dict) -> Pago:
        return services.registrar_pago(
            reserva=validated_data["reserva"],
            monto=validated_data["monto"],
            medio=validated_data["medio"],
            comprobante=validated_data.get("comprobante", ""),
        )


class DevolucionSerializer(serializers.ModelSerializer):
    """Devolución del vehículo al término del arriendo."""

    reserva = serializers.PrimaryKeyRelatedField(queryset=Reserva.objects.all())
    usuario_nombre = serializers.CharField(source="reserva.usuario.nombre_completo", read_only=True)
    vehiculo_patente = serializers.CharField(source="reserva.vehiculo.patente", read_only=True)
    nivel_combustible_display = serializers.CharField(
        source="get_nivel_combustible_display", read_only=True
    )
    kilometros_recorridos = serializers.IntegerField(read_only=True)

    # Entradas que el servicio consume pero que no son campos del modelo.
    cargo_por_danos = serializers.DecimalField(
        max_digits=12, decimal_places=0, required=False, default=Decimal("0"), write_only=True
    )
    dejar_en_mantenimiento = serializers.BooleanField(
        required=False, default=False, write_only=True
    )

    class Meta:
        model = Devolucion
        fields = [
            "id",
            "reserva",
            "usuario_nombre",
            "vehiculo_patente",
            "fecha_devolucion",
            "kilometraje_inicial",
            "kilometraje_final",
            "kilometros_recorridos",
            "nivel_combustible",
            "nivel_combustible_display",
            "danos",
            "cargo_por_danos",
            "cargo_adicional",
            "dias_atraso",
            "dejar_en_mantenimiento",
            "estado_vehiculo_resultante",
            "registrada_en",
        ]
        read_only_fields = [
            "id",
            "kilometraje_inicial",
            "cargo_adicional",
            "dias_atraso",
            "estado_vehiculo_resultante",
            "registrada_en",
        ]

    def create(self, validated_data: dict) -> Devolucion:
        return services.registrar_devolucion(
            reserva=validated_data["reserva"],
            fecha_devolucion=validated_data["fecha_devolucion"],
            kilometraje_final=validated_data["kilometraje_final"],
            nivel_combustible=validated_data["nivel_combustible"],
            danos=validated_data.get("danos", ""),
            cargo_por_danos=validated_data.get("cargo_por_danos") or Decimal("0"),
            dejar_en_mantenimiento=validated_data.get("dejar_en_mantenimiento", False),
        )


class CancelacionSerializer(serializers.Serializer):
    """Motivo opcional de la cancelación de una reserva."""

    motivo = serializers.CharField(required=False, allow_blank=True, default="")
