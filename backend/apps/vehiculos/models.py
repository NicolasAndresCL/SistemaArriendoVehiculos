"""Catálogo de vehículos de la flota."""

from django.core.validators import MinValueValidator
from django.db import models


class Vehiculo(models.Model):
    """Unidad de la flota disponible para arriendo."""

    class Categoria(models.TextChoices):
        CITYCAR = "CITYCAR", "City car"
        SEDAN = "SEDAN", "Sedán"
        SUV = "SUV", "SUV"
        CAMIONETA = "CAMIONETA", "Camioneta"
        FURGON = "FURGON", "Furgón"

    class Transmision(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        AUTOMATICA = "AUTOMATICA", "Automática"

    class Combustible(models.TextChoices):
        BENCINA = "BENCINA", "Bencina"
        DIESEL = "DIESEL", "Diésel"
        HIBRIDO = "HIBRIDO", "Híbrido"
        ELECTRICO = "ELECTRICO", "Eléctrico"

    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        ARRENDADO = "ARRENDADO", "Arrendado"
        MANTENIMIENTO = "MANTENIMIENTO", "En mantenimiento"
        BAJA = "BAJA", "Dado de baja"

    patente = models.CharField(max_length=10, unique=True)
    marca = models.CharField(max_length=40)
    modelo = models.CharField(max_length=40)
    anio = models.PositiveIntegerField("año", validators=[MinValueValidator(1980)])
    categoria = models.CharField(max_length=12, choices=Categoria.choices)
    transmision = models.CharField(
        "transmisión", max_length=12, choices=Transmision.choices, default=Transmision.MANUAL
    )
    combustible = models.CharField(
        max_length=12, choices=Combustible.choices, default=Combustible.BENCINA
    )
    tarifa_diaria = models.DecimalField(
        "tarifa diaria (CLP)", max_digits=10, decimal_places=0, validators=[MinValueValidator(1)]
    )
    kilometraje = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=14, choices=Estado.choices, default=Estado.DISPONIBLE)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "vehículo"
        verbose_name_plural = "vehículos"
        ordering = ["marca", "modelo", "patente"]

    def __str__(self) -> str:
        return f"{self.patente} — {self.marca} {self.modelo}"

    @property
    def descripcion(self) -> str:
        return f"{self.marca} {self.modelo} {self.anio}"

    @property
    def arrendable(self) -> bool:
        """Solo un vehículo disponible puede comprometerse en una reserva nueva."""
        return self.estado == self.Estado.DISPONIBLE
