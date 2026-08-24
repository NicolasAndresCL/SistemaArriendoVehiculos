"""Página de panel: indicadores clave y resumen de actividad reciente."""

from dataclasses import dataclass, field
from typing import Any

from nicegui import ui

from frontend.api_client import ErrorAPI, cliente_api, notificar_error
from frontend.layout import AppLayout
from frontend.theme import aplicar_tema
from frontend.utilidades import formatear_clp, formatear_fecha

ESTADOS_RESERVA_ACTIVA = {"CONFIRMADA", "EN_CURSO"}


@dataclass
class EstadoPanel:
    """Datos agregados que alimentan las tarjetas KPI y las tablas del panel."""

    vehiculos: list[dict[str, Any]] = field(default_factory=list)
    reservas: list[dict[str, Any]] = field(default_factory=list)
    pagos: list[dict[str, Any]] = field(default_factory=list)


async def pagina_panel() -> None:
    """Construye el panel principal con KPIs y tablas resumen."""
    aplicar_tema()
    AppLayout.current().show(ruta_activa="/")

    with ui.column().classes("w-full items-center q-pa-xl") as contenedor_carga:
        ui.spinner(size="lg", color="primary")
        ui.label("Cargando panel...").classes("text-caption")

    estado = EstadoPanel()
    try:
        estado.vehiculos = await cliente_api.listar("vehiculos/")
        estado.reservas = await cliente_api.listar("reservas/")
        estado.pagos = await cliente_api.listar("pagos/")
    except ErrorAPI as exc:
        notificar_error(exc)
        contenedor_carga.clear()
        with contenedor_carga:
            ui.label("No fue posible cargar el panel.").classes("text-negative")
        return

    contenedor_carga.delete()

    disponibles = sum(1 for v in estado.vehiculos if v["estado"] == "DISPONIBLE")
    arrendados = sum(1 for v in estado.vehiculos if v["estado"] == "ARRENDADO")
    mantenimiento = sum(1 for v in estado.vehiculos if v["estado"] == "MANTENIMIENTO")
    activas = sum(1 for r in estado.reservas if r["estado"] in ESTADOS_RESERVA_ACTIVA)
    pendientes = sum(1 for r in estado.reservas if r["estado"] == "PENDIENTE")
    ingresos = sum(float(p["monto"]) for p in estado.pagos if p["estado"] == "PAGADO")

    # El ícono refuerza el significado del KPI sin obligar a leer el rótulo;
    # la bandera `adversa` es lo único que autoriza el uso del rojo.
    tarjetas_kpi = [
        ("Vehículos disponibles", str(disponibles), "check_circle", False),
        ("Vehículos arrendados", str(arrendados), "directions_car", False),
        ("En mantenimiento", str(mantenimiento), "build", mantenimiento > 0),
        ("Reservas activas", str(activas), "event_available", False),
        ("Pendientes de pago", str(pendientes), "schedule", pendientes > 0),
        ("Ingresos totales", formatear_clp(ingresos), "payments", False),
    ]
    with ui.row().classes("w-full gap-3 q-pa-md"):
        for titulo, valor, icono, adversa in tarjetas_kpi:
            clases = "tarjeta-kpi col-grow" + (" tarjeta-kpi-adversa" if adversa else "")
            with ui.column().classes(clases + " gap-1"):
                with ui.row().classes("items-center justify-between w-full no-wrap"):
                    ui.label(titulo).classes("rotulo")
                    ui.icon(icono).classes("icono-kpi").props("size=18px")
                ui.label(valor).classes("valor")

    with ui.row().classes("w-full gap-4 q-px-md q-pb-md items-start"):
        with ui.column().classes("tarjeta-app col q-pa-md"):
            ui.label("Últimas reservas").classes("titulo-seccion q-mb-sm")
            filas_reservas = [
                {
                    "id": r.get("id"),
                    "vehiculo": r.get("vehiculo_patente", ""),
                    "cliente": r.get("usuario_nombre", ""),
                    "estado": r.get("estado_display", ""),
                    "monto": formatear_clp(r.get("monto_estimado")),
                    "creada": formatear_fecha(r.get("creada_en")),
                }
                for r in sorted(
                    estado.reservas, key=lambda r: r.get("creada_en") or "", reverse=True
                )[:8]
            ]
            ui.table(
                columns=[
                    {"name": "vehiculo", "label": "Vehículo", "field": "vehiculo"},
                    {"name": "cliente", "label": "Cliente", "field": "cliente"},
                    {"name": "estado", "label": "Estado", "field": "estado"},
                    {"name": "monto", "label": "Monto", "field": "monto"},
                    {"name": "creada", "label": "Creada", "field": "creada"},
                ],
                rows=filas_reservas,
                row_key="id",
            ).classes("w-full")

        with ui.column().classes("tarjeta-app col q-pa-md"):
            ui.label("Vehículos por estado").classes("titulo-seccion q-mb-sm")
            filas_vehiculos = [
                {
                    "id": v.get("id"),
                    "patente": v.get("patente", ""),
                    "vehiculo": f"{v.get('marca', '')} {v.get('modelo', '')}",
                    "estado": v.get("estado_display", ""),
                }
                for v in estado.vehiculos
            ]
            ui.table(
                columns=[
                    {"name": "patente", "label": "Patente", "field": "patente"},
                    {"name": "vehiculo", "label": "Vehículo", "field": "vehiculo"},
                    {"name": "estado", "label": "Estado", "field": "estado"},
                ],
                rows=filas_vehiculos,
                row_key="id",
            ).classes("w-full")
