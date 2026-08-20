"""Página de registro de pagos de reservas."""

from dataclasses import dataclass, field
from typing import Any

from nicegui import ui
from nicegui.page_arguments import PageArguments

from frontend.api_client import ErrorAPI, cliente_api, notificar_error
from frontend.layout import AppLayout
from frontend.theme import aplicar_tema
from frontend.utilidades import formatear_clp, formatear_fecha

ETIQUETAS_MEDIO = {
    "EFECTIVO": "Efectivo",
    "DEBITO": "Tarjeta de débito",
    "CREDITO": "Tarjeta de crédito",
    "TRANSFERENCIA": "Transferencia",
}
COLOR_ESTADO_PAGO = {"PAGADO": "primary", "ANULADO": "negative"}

COLUMNAS = [
    {"name": "cliente", "label": "Cliente", "field": "cliente", "align": "left"},
    {"name": "vehiculo", "label": "Vehículo", "field": "vehiculo", "align": "left"},
    {"name": "monto", "label": "Monto", "field": "monto", "align": "right"},
    {"name": "medio_display", "label": "Medio de pago", "field": "medio_display"},
    {"name": "comprobante", "label": "Comprobante", "field": "comprobante"},
    {"name": "fecha_pago", "label": "Fecha", "field": "fecha_pago"},
    {"name": "estado_display", "label": "Estado", "field": "estado_display", "align": "center"},
]


@dataclass
class FormularioPago:
    """Estado del formulario de registro de un pago."""

    reserva: int | None = None
    monto: float | None = None
    medio: str = "EFECTIVO"
    comprobante: str = ""

    def reiniciar(self) -> None:
        """Restaura el formulario a sus valores por defecto."""
        self.reserva = None
        self.monto = None
        self.medio = "EFECTIVO"
        self.comprobante = ""


@dataclass
class EstadoPagos:
    """Datos cargados de la API y formulario activo del diálogo."""

    pagos: list[dict[str, Any]] = field(default_factory=list)
    reservas_pendientes: list[dict[str, Any]] = field(default_factory=list)
    formulario: FormularioPago = field(default_factory=FormularioPago)


def _obtener_reserva_de_query(args: PageArguments) -> str | None:
    """Extrae el parámetro ``reserva`` de la URL, si viene desde otra página."""
    valor = args.query_parameters.get("reserva")
    if isinstance(valor, list):
        return valor[0] if valor else None
    return valor


async def pagina_pagos(args: PageArguments) -> None:
    """Construye la página de registro de pagos."""
    aplicar_tema()
    AppLayout.current().show()

    estado = EstadoPagos()

    async def cargar() -> None:
        try:
            estado.pagos = await cliente_api.listar("pagos/")
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        tabla.rows = [construir_fila(p) for p in estado.pagos]
        tabla.update()

    def construir_fila(pago: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": pago.get("id"),
            "cliente": pago.get("usuario_nombre", ""),
            "vehiculo": pago.get("vehiculo_patente", ""),
            "monto": formatear_clp(pago.get("monto")),
            "medio_display": pago.get("medio_display", ""),
            "comprobante": pago.get("comprobante", "") or "-",
            "fecha_pago": formatear_fecha(pago.get("fecha_pago")),
            "estado_display": pago.get("estado_display", ""),
            "estado_color": COLOR_ESTADO_PAGO.get(pago.get("estado", ""), "primary"),
        }

    def etiqueta_reserva(reserva: dict[str, Any]) -> str:
        return (
            f"{reserva.get('vehiculo_patente', '')} - {reserva.get('usuario_nombre', '')} "
            f"({formatear_clp(reserva.get('monto_estimado'))})"
        )

    def actualizar_monto_propuesto() -> None:
        reserva = next(
            (r for r in estado.reservas_pendientes if r["id"] == estado.formulario.reserva),
            None,
        )
        if reserva is not None:
            campo_monto.value = reserva.get("monto_estimado")

    async def abrir_nuevo(reserva_preseleccionada: int | None = None) -> None:
        estado.formulario.reiniciar()
        try:
            estado.reservas_pendientes = await cliente_api.listar(
                "reservas/", params={"estado": "PENDIENTE"}
            )
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        opciones = {r["id"]: etiqueta_reserva(r) for r in estado.reservas_pendientes}
        selector_reserva.set_options(opciones)
        if reserva_preseleccionada and reserva_preseleccionada in opciones:
            selector_reserva.value = reserva_preseleccionada
        else:
            selector_reserva.value = None
        campo_medio.value = "EFECTIVO"
        campo_comprobante.value = ""
        actualizar_monto_propuesto()
        dialogo.open()

    async def guardar() -> None:
        formulario = estado.formulario
        if not formulario.reserva:
            ui.notify("Seleccione una reserva pendiente de pago.", type="warning")
            return
        datos = {
            "reserva": formulario.reserva,
            "monto": formulario.monto,
            "medio": formulario.medio,
            "comprobante": formulario.comprobante,
        }
        try:
            await cliente_api.crear("pagos/", datos)
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        ui.notify("Pago registrado correctamente.", type="positive")
        dialogo.close()
        await cargar()

    with ui.row().classes("w-full items-center justify-between q-pa-md"):
        ui.label("Pagos").classes("text-h6")
        ui.button("Nuevo pago", icon="add", on_click=lambda: abrir_nuevo())

    with ui.column().classes("tarjeta-app q-mx-md q-mb-md q-pa-sm"):
        tabla = ui.table(columns=COLUMNAS, rows=[], row_key="id").classes("w-full")

        with tabla.add_slot("body-cell-estado_display"):
            with tabla.cell("estado_display"):
                ui.badge().props(':label="props.value" :color="props.row.estado_color"')

    with ui.dialog() as dialogo, ui.card().classes("q-pa-md").style("min-width: 420px"):
        ui.label("Registrar pago").classes("text-subtitle1 text-weight-medium")
        formulario = estado.formulario
        with ui.column().classes("w-full gap-2"):
            selector_reserva = (
                ui.select({}, label="Reserva pendiente de pago")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "reserva")
            )
            selector_reserva.on_value_change(actualizar_monto_propuesto)
            campo_monto = (
                ui.number("Monto (CLP)")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "monto")
            )
            campo_medio = (
                ui.select(ETIQUETAS_MEDIO, label="Medio de pago")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "medio")
            )
            campo_comprobante = (
                ui.input("Número de comprobante")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "comprobante")
            )
        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Registrar pago", on_click=guardar, color="primary")

    await cargar()

    reserva_query = _obtener_reserva_de_query(args)
    if reserva_query:
        try:
            await abrir_nuevo(int(reserva_query))
        except ValueError:
            pass
