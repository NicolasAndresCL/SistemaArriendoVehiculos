"""Carga de datos de demostración.

Idempotente: se puede ejecutar tantas veces como haga falta sin duplicar nada,
porque todo pasa por `get_or_create`. El CI la usa en el job de arranque.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.arriendos import services
from apps.arriendos.models import Pago, Reserva
from apps.usuarios.models import Usuario
from apps.vehiculos.models import Vehiculo

# Credencial por defecto del sistema, según el enunciado.
EMAIL_ADMIN = "admin@estacionamiento.cl"
PASSWORD_ADMIN = "1234"

VEHICULOS = [
    ("JKLM12", "Toyota", "Yaris", 2022, "CITYCAR", "MANUAL", "BENCINA", 28000, 41200),
    ("BCDF34", "Hyundai", "Accent", 2021, "SEDAN", "AUTOMATICA", "BENCINA", 32000, 63500),
    ("GHJK56", "Kia", "Sportage", 2023, "SUV", "AUTOMATICA", "DIESEL", 52000, 18900),
    ("LPRS78", "Chevrolet", "Sail", 2020, "CITYCAR", "MANUAL", "BENCINA", 24000, 88400),
    ("TVWX90", "Nissan", "Navara", 2022, "CAMIONETA", "AUTOMATICA", "DIESEL", 65000, 54300),
    ("ZBCD11", "Suzuki", "Swift", 2023, "CITYCAR", "MANUAL", "BENCINA", 26000, 12100),
    ("FGHJ22", "Toyota", "RAV4", 2024, "SUV", "AUTOMATICA", "HIBRIDO", 74000, 6800),
    ("KLPR33", "Peugeot", "Partner", 2021, "FURGON", "MANUAL", "DIESEL", 38000, 97600),
]

CLIENTES = [
    ("tais.montesinos@ejemplo.cl", "18.234.567-8", "Tais", "Montesinos", "+56 9 8123 4567", 900),
    (
        "joaquin.argandona@ejemplo.cl",
        "19.876.543-2",
        "Joaquín",
        "Argandoña",
        "+56 9 7654 3210",
        400,
    ),
    ("martin.rojas@ejemplo.cl", "17.345.678-9", "Martín", "Rojas", "+56 9 6543 2109", -30),
]


class Command(BaseCommand):
    help = "Carga usuarios, vehículos y arriendos de demostración."

    @transaction.atomic
    def handle(self, *args, **opciones) -> None:
        hoy = date.today()

        admin, creado = Usuario.objects.get_or_create(
            email=EMAIL_ADMIN,
            defaults={
                "rut": "11.111.111-1",
                "nombre": "Administrador",
                "apellido": "del Sistema",
                "telefono": "+56 2 2345 6789",
                "rol": Usuario.Rol.OPERADOR,
                "is_staff": True,
                "is_superuser": True,
                "licencia_numero": "A-11111111",
                "licencia_vencimiento": hoy + timedelta(days=1825),
            },
        )
        if creado:
            # create_superuser no ejecuta los validadores de contraseña, que es
            # justamente lo que permite la clave "1234" que pide el enunciado.
            admin.set_password(PASSWORD_ADMIN)
            admin.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(f"Administrador creado: {EMAIL_ADMIN} / 1234"))
        else:
            self.stdout.write(f"El administrador {EMAIL_ADMIN} ya existía.")

        clientes = []
        for email, rut, nombre, apellido, telefono, dias_licencia in CLIENTES:
            cliente, nuevo = Usuario.objects.get_or_create(
                email=email,
                defaults={
                    "rut": rut,
                    "nombre": nombre,
                    "apellido": apellido,
                    "telefono": telefono,
                    "rol": Usuario.Rol.CLIENTE,
                    "licencia_numero": f"B-{rut[:2]}{rut[3:6]}",
                    # El tercer cliente queda con la licencia vencida a
                    # propósito: así la regla que rechaza esa reserva es
                    # visible en la demostración.
                    "licencia_vencimiento": hoy + timedelta(days=dias_licencia),
                },
            )
            if nuevo:
                cliente.set_password("1234")
                cliente.save(update_fields=["password"])
            clientes.append(cliente)

        vehiculos = []
        for patente, marca, modelo, anio, cat, trans, comb, tarifa, km in VEHICULOS:
            vehiculo, _ = Vehiculo.objects.get_or_create(
                patente=patente,
                defaults={
                    "marca": marca,
                    "modelo": modelo,
                    "anio": anio,
                    "categoria": cat,
                    "transmision": trans,
                    "combustible": comb,
                    "tarifa_diaria": Decimal(tarifa),
                    "kilometraje": km,
                },
            )
            vehiculos.append(vehiculo)

        # Un vehículo en mantenimiento para que el catálogo no se vea uniforme.
        ultimo = vehiculos[-1]
        if ultimo.estado == Vehiculo.Estado.DISPONIBLE and not ultimo.reservas.exists():
            ultimo.estado = Vehiculo.Estado.MANTENIMIENTO
            ultimo.save(update_fields=["estado"])

        if Reserva.objects.exists():
            self.stdout.write("Ya había reservas cargadas: no se crean más.")
            self._resumen()
            return

        # Reserva pendiente de pago.
        services.crear_reserva(
            usuario=clientes[0],
            vehiculo=vehiculos[0],
            fecha_inicio=hoy + timedelta(days=3),
            fecha_fin=hoy + timedelta(days=7),
            observaciones="Solicita silla para menor.",
        )

        # Reserva pagada y confirmada.
        confirmada = services.crear_reserva(
            usuario=clientes[1],
            vehiculo=vehiculos[1],
            fecha_inicio=hoy + timedelta(days=1),
            fecha_fin=hoy + timedelta(days=5),
        )
        services.registrar_pago(
            reserva=confirmada,
            monto=confirmada.monto_estimado,
            medio=Pago.Medio.CREDITO,
            comprobante="TRX-000123",
        )

        # Arriendo en curso: pagado y con el vehículo ya retirado.
        en_curso = services.crear_reserva(
            usuario=clientes[0],
            vehiculo=vehiculos[2],
            fecha_inicio=hoy - timedelta(days=2),
            fecha_fin=hoy + timedelta(days=2),
        )
        services.registrar_pago(
            reserva=en_curso,
            monto=en_curso.monto_estimado,
            medio=Pago.Medio.TRANSFERENCIA,
            comprobante="TRX-000124",
        )
        services.registrar_retiro(reserva=en_curso)

        # Arriendo ya cerrado, con devolución registrada.
        cerrada = services.crear_reserva(
            usuario=clientes[1],
            vehiculo=vehiculos[3],
            fecha_inicio=hoy - timedelta(days=10),
            fecha_fin=hoy - timedelta(days=6),
        )
        services.registrar_pago(
            reserva=cerrada,
            monto=cerrada.monto_estimado,
            medio=Pago.Medio.DEBITO,
            comprobante="TRX-000120",
        )
        services.registrar_retiro(reserva=cerrada)
        services.registrar_devolucion(
            reserva=cerrada,
            fecha_devolucion=hoy - timedelta(days=5),
            kilometraje_final=vehiculos[3].kilometraje + 620,
            nivel_combustible="TRES_CUARTOS",
            danos="",
        )

        self._resumen()

    def _resumen(self) -> None:
        self.stdout.write(
            self.style.SUCCESS(
                f"Datos de demostración listos: {Usuario.objects.count()} usuarios, "
                f"{Vehiculo.objects.count()} vehículos, {Reserva.objects.count()} reservas."
            )
        )
