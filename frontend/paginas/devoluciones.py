"""Página de registro de devoluciones de vehículos."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from nicegui import ui
from nicegui.page_arguments import PageArguments

from frontend.api_client import ErrorAPI, cliente_api, notificar_error
from frontend.layout import AppLayout
from frontend.theme import aplicar_tema
from frontend.utilidades import formatear_clp, formatear_fecha, formatear_kilometros

ESTADOS_RESERVA_ELEGIBLES = {"CONFIRMADA", "EN_CURSO"}

ETIQUETAS_NIVEL_COMBUSTIBLE = {
    "VACIO": "Vacío",
    "UN_CUARTO": "1/4",
    "MEDIO": "1/2",
    "TRES_CUARTOS": "3/4",
    "LLENO": "Lleno",
}

COLUMNAS = [
    {"name": "cliente", "label": "Cliente", "field": "cliente", "align": "left"},
    {"name": "vehiculo", "label": "Vehículo", "field": "vehiculo", "align": "left"},
    {"name": "fecha_devolucion", "label": "Fecha devolución", "field": "fecha_devolucion"},
    {"name": "kilometros", "label": "Km recorridos", "field": "kilometros", "align": "right"},
    {"name": "combustible", "label": "Combustible", "field": "combustible"},
    {"name": "cargo", "label": "Cargo adicional", "field": "cargo", "align": "right"},
    {"name": "dias_atraso", "label": "Días de atraso", "field": "dias_atraso", "align": "right"},
    {"name": "estado_resultante", "label": "Estado del vehículo", "field": "estado_resultante"},
]


def _calcular_dias_atraso(fecha_fin: str, fecha_devolucion: str) -> int:
    """Calcula los días de atraso entre el fin de reserva y la devolución."""
    try:
        fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
        devolucion = datetime.strptime(fecha_devolucion, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return 0
    return max((devolucion - fin).days, 0)


def _obtener_reserva_de_query(args: PageArguments) -> str | None:
    """Extrae el parámetro ``reserva`` de la URL, si viene desde otra página."""
    valor = args.query_parameters.get("reserva")
    if isinstance(valor, list):
        return valor[0] if valor else None
    return valor


@dataclass
class FormularioDevolucion:
    """Estado del formulario de registro de una devolución."""

    reserva: int | None = None
    fecha_devolucion: str = field(default_factory=lambda: date.today().isoformat())
    kilometraje_final: int | None = None
    nivel_combustible: str = "MEDIO"
    danos: str = ""
    cargo_por_danos: float | None = 0
    dejar_en_mantenimiento: bool = False

    def reiniciar(self) -> None:
        """Restaura el formulario a sus valores por defecto."""
        self.reserva = None
        self.fecha_devolucion = date.today().isoformat()
        self.kilometraje_final = None
        self.nivel_combustible = "MEDIO"
        self.danos = ""
        self.cargo_por_danos = 0
        self.dejar_en_mantenimiento = False


@dataclass
class EstadoDevoluciones:
    """Datos cargados de la API y formulario activo del diálogo."""

    devoluciones: list[dict[str, Any]] = field(default_factory=list)
    reservas_elegibles: list[dict[str, Any]] = field(default_factory=list)
    formulario: FormularioDevolucion = field(default_factory=FormularioDevolucion)


async def pagina_devoluciones(args: PageArguments) -> None:
    """Construye la página de registro de devoluciones."""
    aplicar_tema()
    AppLayout.current().show()

    estado = EstadoDevoluciones()

    async def cargar() -> None:
        try:
            estado.devoluciones = await cliente_api.listar("devoluciones/")
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        tabla.rows = [construir_fila(d) for d in estado.devoluciones]
        tabla.update()

    def construir_fila(devolucion: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": devolucion.get("id"),
            "cliente": devolucion.get("usuario_nombre", ""),
            "vehiculo": devolucion.get("vehiculo_patente", ""),
            "fecha_devolucion": formatear_fecha(devolucion.get("fecha_devolucion")),
            "kilometros": formatear_kilometros(devolucion.get("kilometros_recorridos")),
            "combustible": devolucion.get("nivel_combustible_display", ""),
            "cargo": formatear_clp(devolucion.get("cargo_adicional")),
            "dias_atraso": devolucion.get("dias_atraso", 0),
            "estado_resultante": devolucion.get("estado_vehiculo_resultante", ""),
        }

    def etiqueta_reserva(reserva: dict[str, Any]) -> str:
        return (
            f"{reserva.get('vehiculo_patente', '')} - {reserva.get('usuario_nombre', '')} "
            f"(fin: {formatear_fecha(reserva.get('fecha_fin'))})"
        )

    def actualizar_atraso() -> None:
        reserva = next(
            (r for r in estado.reservas_elegibles if r["id"] == estado.formulario.reserva),
            None,
        )
        if reserva is None:
            etiqueta_atraso.set_text("Días de atraso estimados: -")
            return
        dias = _calcular_dias_atraso(
            reserva.get("fecha_fin", ""), estado.formulario.fecha_devolucion
        )
        if dias > 0:
            etiqueta_atraso.set_text(f"Días de atraso estimados: {dias}")
            etiqueta_atraso.classes(replace="text-weight-medium text-negative")
        else:
            etiqueta_atraso.set_text("Días de atraso estimados: 0 (a tiempo)")
            etiqueta_atraso.classes(replace="text-weight-medium")

    async def abrir_nuevo(reserva_preseleccionada: int | None = None) -> None:
        estado.formulario.reiniciar()
        try:
            todas = await cliente_api.listar("reservas/")
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        estado.reservas_elegibles = [
            r for r in todas if r.get("estado") in ESTADOS_RESERVA_ELEGIBLES
        ]
        opciones = {r["id"]: etiqueta_reserva(r) for r in estado.reservas_elegibles}
        selector_reserva.set_options(opciones)
        if reserva_preseleccionada and reserva_preseleccionada in opciones:
            selector_reserva.value = reserva_preseleccionada
        else:
            selector_reserva.value = None
        campo_fecha.value = estado.formulario.fecha_devolucion
        campo_kilometraje.value = None
        campo_combustible.value = "MEDIO"
        campo_danos.value = ""
        campo_cargo.value = 0
        campo_mantenimiento.value = False
        actualizar_atraso()
        dialogo.open()

    async def guardar() -> None:
        formulario = estado.formulario
        if not formulario.reserva:
            ui.notify("Seleccione una reserva confirmada o en curso.", type="warning")
            return
        datos = {
            "reserva": formulario.reserva,
            "fecha_devolucion": formulario.fecha_devolucion,
            "kilometraje_final": formulario.kilometraje_final,
            "nivel_combustible": formulario.nivel_combustible,
            "danos": formulario.danos,
            "cargo_por_danos": formulario.cargo_por_danos,
            "dejar_en_mantenimiento": formulario.dejar_en_mantenimiento,
        }
        try:
            await cliente_api.crear("devoluciones/", datos)
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        ui.notify("Devolución registrada correctamente.", type="positive")
        dialogo.close()
        await cargar()

    with ui.row().classes("w-full items-center justify-between q-pa-md"):
        ui.label("Devoluciones").classes("text-h6")
        ui.button("Nueva devolución", icon="add", on_click=lambda: abrir_nuevo())

    with ui.column().classes("tarjeta-app q-mx-md q-mb-md q-pa-sm"):
        tabla = ui.table(columns=COLUMNAS, rows=[], row_key="id").classes("w-full")

    with ui.dialog() as dialogo, ui.card().classes("q-pa-md").style("min-width: 440px"):
        ui.label("Registrar devolución").classes("text-subtitle1 text-weight-medium")
        formulario = estado.formulario
        with ui.column().classes("w-full gap-2"):
            selector_reserva = (
                ui.select({}, label="Reserva confirmada o en curso")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "reserva")
            )
            selector_reserva.on_value_change(actualizar_atraso)
            campo_fecha = (
                ui.date_input("Fecha de devolución", value=date.today().isoformat())
                .classes("w-full")
                .bind_value(formulario, "fecha_devolucion")
            )
            campo_fecha.on_value_change(actualizar_atraso)
            etiqueta_atraso = ui.label("Días de atraso estimados: -").classes("text-weight-medium")
            campo_kilometraje = (
                ui.number("Kilometraje final", format="%.0f")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "kilometraje_final")
            )
            campo_combustible = (
                ui.select(ETIQUETAS_NIVEL_COMBUSTIBLE, label="Nivel de combustible")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "nivel_combustible")
            )
            campo_danos = (
                ui.textarea("Daños observados")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "danos")
            )
            campo_cargo = (
                ui.number("Cargo por daños (CLP)")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "cargo_por_danos")
            )
            campo_mantenimiento = ui.switch("Dejar vehículo en mantenimiento").bind_value(
                formulario, "dejar_en_mantenimiento"
            )
        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Registrar devolución", on_click=guardar, color="primary")

    await cargar()

    reserva_query = _obtener_reserva_de_query(args)
    if reserva_query:
        try:
            await abrir_nuevo(int(reserva_query))
        except ValueError:
            pass
