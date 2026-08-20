"""Serializers del catálogo de vehículos."""

from rest_framework import serializers

from .models import Vehiculo


class VehiculoSerializer(serializers.ModelSerializer):
    """Representación de un vehículo.

    Los campos `*_display` acompañan a los códigos para que la interfaz muestre
    la etiqueta en español sin duplicar el diccionario de opciones.
    """

    descripcion = serializers.CharField(read_only=True)
    categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)
    transmision_display = serializers.CharField(source="get_transmision_display", read_only=True)
    combustible_display = serializers.CharField(source="get_combustible_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = Vehiculo
        fields = [
            "id",
            "patente",
            "marca",
            "modelo",
            "anio",
            "descripcion",
            "categoria",
            "categoria_display",
            "transmision",
            "transmision_display",
            "combustible",
            "combustible_display",
            "tarifa_diaria",
            "kilometraje",
            "estado",
            "estado_display",
            "observaciones",
        ]
        read_only_fields = ["id"]

    def validate_patente(self, value: str) -> str:
        """Normaliza la patente: siempre en mayúsculas y sin espacios."""
        return value.strip().upper().replace(" ", "")
