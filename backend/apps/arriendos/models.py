"""Agregado de arriendo: reserva, pago y devolución.

`Pago` y `Devolucion` no existen sin su `Reserva`: viven en la misma app porque
comparten un único ciclo de vida.

Máquina de estados de la reserva:

    PENDIENTE --pago--> CONFIRMADA --retiro--> EN_CURSO --devolución--> FINALIZADA
        |                    |
        +--------------------+--> CANCELADA

Las transiciones NO se hacen asignando `estado` desde una vista: viven en
`services.py`, que es quien valida las reglas y lanza si no se cumplen.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Reserva(models.Model):
    """Compromiso de un vehículo para un cliente durante un período."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de pago"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        EN_CURSO = "EN_CURSO", "En curso"
        FINALIZADA = "FINALIZADA", "Finalizada"
        CANCELADA = "CANCELADA", "Cancelada"

    # Estados en los que la reserva ocupa el vehículo y bloquea otras reservas.
    ESTADOS_ACTIVOS = (Estado.PENDIENTE, Estado.CONFIRMADA, Estado.EN_CURSO)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservas"
    )
    vehiculo = models.ForeignKey(
        "vehiculos.Vehiculo", on_delete=models.PROTECT, related_name="reservas"
    )
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_fin = models.DateField("fecha de término")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    monto_estimado = models.DecimalField(
        "monto estimado (CLP)", max_digits=12, decimal_places=0, default=0
    )
    observaciones = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-creada_en"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fecha_fin__gt=models.F("fecha_inicio")),
                name="reserva_fecha_fin_posterior_a_inicio",
            ),
        ]

    def __str__(self) -> str:
        return f"Reserva #{self.pk} · {self.vehiculo.patente} · {self.get_estado_display()}"

    @property
    def dias(self) -> int:
        """Días facturables. Un arriendo dentro del mismo día cobra un día."""
        return max(1, (self.fecha_fin - self.fecha_inicio).days)

    @property
    def esta_activa(self) -> bool:
        return self.estado in self.ESTADOS_ACTIVOS


class Pago(models.Model):
    """Registro del cobro asociado a una reserva."""

    class Medio(models.TextChoices):
        EFECTIVO = "EFECTIVO", "Efectivo"
        DEBITO = "DEBITO", "Tarjeta de débito"
        CREDITO = "CREDITO", "Tarjeta de crédito"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"

    class Estado(models.TextChoices):
        PAGADO = "PAGADO", "Pagado"
        ANULADO = "ANULADO", "Anulado"

    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name="pagos")
    monto = models.DecimalField(
        "monto (CLP)", max_digits=12, decimal_places=0, validators=[MinValueValidator(1)]
    )
    medio = models.CharField(max_length=14, choices=Medio.choices)
    estado = models.CharField(max_length=8, choices=Estado.choices, default=Estado.PAGADO)
    comprobante = models.CharField(max_length=40, blank=True)
    fecha_pago = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        ordering = ["-fecha_pago"]

    def __str__(self) -> str:
        return f"Pago #{self.pk} · reserva {self.reserva_id} · ${self.monto:,.0f}"


class Devolucion(models.Model):
    """Cierre del arriendo: entrega del vehículo por parte del cliente."""

    class NivelCombustible(models.TextChoices):
        VACIO = "VACIO", "Vacío"
        UN_CUARTO = "UN_CUARTO", "1/4"
        MEDIO = "MEDIO", "1/2"
        TRES_CUARTOS = "TRES_CUARTOS", "3/4"
        LLENO = "LLENO", "Lleno"

    # OneToOne: una reserva se devuelve una sola vez. La restricción vive en la
    # base de datos, no solo en la validación de la vista.
    reserva = models.OneToOneField(Reserva, on_delete=models.CASCADE, related_name="devolucion")
    fecha_devolucion = models.DateField("fecha de devolución")
    # Se congela el kilometraje del vehículo al momento de registrar la
    # devolución: después el vehículo queda con el final y la diferencia se
    # perdería.
    kilometraje_inicial = models.PositiveIntegerField(default=0)
    kilometraje_final = models.PositiveIntegerField()
    nivel_combustible = models.CharField(
        "nivel de combustible",
        max_length=14,
        choices=NivelCombustible.choices,
        default=NivelCombustible.LLENO,
    )
    danos = models.TextField("daños observados", blank=True)
    cargo_adicional = models.DecimalField(
        "cargo adicional (CLP)", max_digits=12, decimal_places=0, default=0
    )
    dias_atraso = models.PositiveIntegerField("días de atraso", default=0)
    estado_vehiculo_resultante = models.CharField(max_length=14)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "devolución"
        verbose_name_plural = "devoluciones"
        ordering = ["-registrada_en"]

    def __str__(self) -> str:
        return f"Devolución de la reserva #{self.reserva_id} el {self.fecha_devolucion}"

    @property
    def kilometros_recorridos(self) -> int:
        return max(0, self.kilometraje_final - self.kilometraje_inicial)
