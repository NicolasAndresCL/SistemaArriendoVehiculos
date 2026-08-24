"""Página de administración de reservas."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from nicegui import ui

from frontend.api_client import ErrorAPI, cliente_api, notificar_error
from frontend.layout import AppLayout
from frontend.theme import aplicar_tema
from frontend.utilidades import formatear_clp, formatear_fecha, hoy_iso

ETIQUETAS_ESTADO = {
    "PENDIENTE": "Pendiente de pago",
    "CONFIRMADA": "Confirmada",
    "EN_CURSO": "En curso",
    "FINALIZADA": "Finalizada",
    "CANCELADA": "Cancelada",
}
COLOR_ESTADO = {
    "PENDIENTE": "secondary",
    "CONFIRMADA": "primary",
    "EN_CURSO": "primary",
    "FINALIZADA": "primary",
    "CANCELADA": "negative",
}

COLUMNAS = [
    {"name": "cliente", "label": "Cliente", "field": "cliente", "align": "left"},
    {"name": "vehiculo", "label": "Vehículo", "field": "vehiculo", "align": "left"},
    {"name": "fechas", "label": "Fechas", "field": "fechas", "align": "left"},
    {"name": "dias", "label": "Días", "field": "dias", "align": "right"},
    {"name": "monto", "label": "Monto estimado", "field": "monto", "align": "right"},
    {"name": "estado_display", "label": "Estado", "field": "estado_display", "align": "center"},
    {"name": "pagada", "label": "Pagada", "field": "pagada", "align": "center"},
    {"name": "acciones", "label": "Acciones", "field": "acciones", "align": "center"},
]


def _ocultar_si_no(campo: str) -> str:
    """Prop que oculta un botón cuando la fila no admite esa acción.

    Se usa un binding de clase y no `v-if`: `v-if` es una directiva de
    compilación de Vue, y NiceGUI entrega las props como atributos, así que
    nunca llega a evaluarse y todos los botones quedarían visibles.
    """
    return f":class=\"props.row.{campo} ? '' : 'hidden'\""


def _calcular_dias(fecha_inicio: str, fecha_fin: str) -> int:
    """Calcula la cantidad de días entre dos fechas ISO ``aaaa-mm-dd``."""
    try:
        inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
        fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return 0
    return max((fin - inicio).days, 0)


@dataclass
class FormularioReserva:
    """Estado del formulario de creación de una reserva."""

    usuario: int | None = None
    vehiculo: int | None = None
    fecha_inicio: str = field(default_factory=hoy_iso)
    fecha_fin: str = field(default_factory=hoy_iso)
    observaciones: str = ""

    def reiniciar(self) -> None:
        """Restaura el formulario a sus valores por defecto."""
        self.usuario = None
        self.vehiculo = None
        self.fecha_inicio = hoy_iso()
        self.fecha_fin = hoy_iso()
        self.observaciones = ""


@dataclass
class EstadoReservas:
    """Datos cargados de la API y filtro activo de la página."""

    reservas: list[dict[str, Any]] = field(default_factory=list)
    usuarios: list[dict[str, Any]] = field(default_factory=list)
    vehiculos_disponibles: list[dict[str, Any]] = field(default_factory=list)
    formulario: FormularioReserva = field(default_factory=FormularioReserva)
    filtro_estado: str = ""


async def pagina_reservas() -> None:
    """Construye la página de administración de reservas."""
    aplicar_tema()
    AppLayout.current().show(ruta_activa="/reservas")

    estado = EstadoReservas()

    async def cargar() -> None:
        params = {"estado": estado.filtro_estado} if estado.filtro_estado else None
        try:
            estado.reservas = await cliente_api.listar("reservas/", params=params)
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        tabla.rows = [construir_fila(r) for r in estado.reservas]
        tabla.update()

    def construir_fila(reserva: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": reserva.get("id"),
            "cliente": reserva.get("usuario_nombre", ""),
            "vehiculo": f"{reserva.get('vehiculo_patente', '')} - "
            f"{reserva.get('vehiculo_descripcion', '')}",
            "fechas": f"{formatear_fecha(reserva.get('fecha_inicio'))} a "
            f"{formatear_fecha(reserva.get('fecha_fin'))}",
            "dias": reserva.get("dias", 0),
            "monto": formatear_clp(reserva.get("monto_estimado")),
            "estado": reserva.get("estado", ""),
            "estado_display": reserva.get("estado_display", ""),
            "estado_color": COLOR_ESTADO.get(reserva.get("estado", ""), "primary"),
            "pagada": reserva.get("pagada", False),
            # Qué acciones admite la reserva según su estado. Se calculan aquí,
            # en Python, y no con una directiva `v-if` dentro de `.props()`:
            # `v-if` es una directiva de compilación de Vue y NiceGUI la
            # entrega como un atributo más, así que no se evalúa nunca y todos
            # los botones terminan visibles en todas las filas.
            "puede_pagar": reserva.get("estado") == "PENDIENTE",
            "puede_retirar": reserva.get("estado") == "CONFIRMADA",
            "puede_devolver": reserva.get("estado") in ("CONFIRMADA", "EN_CURSO"),
            "puede_cancelar": reserva.get("estado") in ("PENDIENTE", "CONFIRMADA", "EN_CURSO"),
        }

    async def abrir_nuevo() -> None:
        estado.formulario.reiniciar()
        try:
            estado.usuarios = await cliente_api.listar("usuarios/")
            estado.vehiculos_disponibles = await cliente_api.listar(
                "vehiculos/", params={"estado": "DISPONIBLE"}
            )
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        opciones_usuario = {
            u["id"]: f"{u.get('nombre_completo', '')} ({u.get('email', '')})"
            for u in estado.usuarios
        }
        opciones_vehiculo = {
            v["id"]: f"{v.get('patente', '')} - {v.get('marca', '')} {v.get('modelo', '')}"
            for v in estado.vehiculos_disponibles
        }
        selector_usuario.set_options(opciones_usuario)
        selector_vehiculo.set_options(opciones_vehiculo)
        selector_usuario.value = None
        selector_vehiculo.value = None
        campo_fecha_inicio.value = estado.formulario.fecha_inicio
        campo_fecha_fin.value = estado.formulario.fecha_fin
        campo_observaciones.value = ""
        actualizar_monto_estimado()
        dialogo.open()

    def actualizar_monto_estimado() -> None:
        dias = _calcular_dias(estado.formulario.fecha_inicio, estado.formulario.fecha_fin)
        vehiculo = next(
            (v for v in estado.vehiculos_disponibles if v["id"] == estado.formulario.vehiculo),
            None,
        )
        tarifa = float(vehiculo["tarifa_diaria"]) if vehiculo else 0.0
        etiqueta_monto.set_text(f"Monto estimado: {formatear_clp(dias * tarifa)} ({dias} días)")

    async def crear_reserva() -> None:
        formulario = estado.formulario
        if not formulario.usuario or not formulario.vehiculo:
            ui.notify("Seleccione un cliente y un vehículo.", type="warning")
            return
        datos = {
            "usuario": formulario.usuario,
            "vehiculo": formulario.vehiculo,
            "fecha_inicio": formulario.fecha_inicio,
            "fecha_fin": formulario.fecha_fin,
            "observaciones": formulario.observaciones,
        }
        try:
            await cliente_api.crear("reservas/", datos)
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        ui.notify("Reserva creada correctamente.", type="positive")
        dialogo.close()
        await cargar()

    async def retirar(reserva_id: int) -> None:
        try:
            await cliente_api.accion("reservas/", reserva_id, "retirar")
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        ui.notify("Vehículo retirado. La reserva está en curso.", type="positive")
        await cargar()

    def ir_a_pago(reserva_id: int) -> None:
        ui.navigate.to(f"/pagos?reserva={reserva_id}")

    def ir_a_devolucion(reserva_id: int) -> None:
        ui.navigate.to(f"/devoluciones?reserva={reserva_id}")

    async def confirmar_cancelacion(reserva_id: int) -> None:
        motivo = {"texto": ""}
        with ui.dialog() as confirmacion, ui.card().style("min-width: 360px"):
            ui.label("Cancelar reserva").classes("text-subtitle1 text-weight-medium")
            ui.label("Esta acción no se puede deshacer.").classes("text-caption")
            campo_motivo = (
                ui.input("Motivo de la cancelación")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(motivo, "texto")
            )
            with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
                ui.button("Volver", on_click=confirmacion.close).props("flat")

                async def cancelar() -> None:
                    try:
                        await cliente_api.accion(
                            "reservas/", reserva_id, "cancelar", {"motivo": motivo["texto"]}
                        )
                    except ErrorAPI as exc:
                        notificar_error(exc)
                        return
                    ui.notify("Reserva cancelada.", type="positive")
                    confirmacion.close()
                    await cargar()

                ui.button("Cancelar reserva", on_click=cancelar, color="negative")
        campo_motivo.on("keydown.enter", cancelar)
        confirmacion.open()

    with ui.row().classes("w-full items-center justify-between q-pa-md"):
        ui.label("Reservas").classes("text-h6")
        with ui.row().classes("items-center gap-2"):
            selector_filtro = (
                ui.select({"": "Todos los estados", **ETIQUETAS_ESTADO}, value="")
                .props("outlined dense")
                .style("min-width: 220px")
            )
            ui.button("Nueva reserva", icon="add", on_click=abrir_nuevo)

    async def cambiar_filtro() -> None:
        estado.filtro_estado = selector_filtro.value or ""
        await cargar()

    selector_filtro.on_value_change(cambiar_filtro)

    with ui.column().classes("tarjeta-app q-mx-md q-mb-md q-pa-sm"):
        tabla = ui.table(columns=COLUMNAS, rows=[], row_key="id").classes("w-full")

        with tabla.add_slot("body-cell-estado_display"):
            with tabla.cell("estado_display"):
                ui.badge().props(':label="props.value" :color="props.row.estado_color"')

        with tabla.add_slot("body-cell-pagada"):
            with tabla.cell("pagada"):
                ui.badge().props(
                    ":label=\"props.value ? 'Sí' : 'No'\" "
                    ":color=\"props.value ? 'primary' : 'secondary'\""
                )

        with tabla.add_slot("body-cell-acciones"):
            with tabla.cell("acciones"):
                with ui.row().classes("gap-1 justify-center flex-nowrap"):
                    ui.button(icon="payments").props(
                        "flat dense round color=primary " + _ocultar_si_no("puede_pagar")
                    ).tooltip("Registrar pago").on(
                        "click",
                        js_handler="() => emit(props.row.id)",
                        handler=lambda e: ir_a_pago(e.args),
                    )
                    ui.button(icon="directions_car").props(
                        "flat dense round color=primary " + _ocultar_si_no("puede_retirar")
                    ).tooltip("Retirar vehículo").on(
                        "click",
                        js_handler="() => emit(props.row.id)",
                        handler=lambda e: retirar(e.args),
                    )
                    ui.button(icon="assignment_return").props(
                        "flat dense round color=primary " + _ocultar_si_no("puede_devolver")
                    ).tooltip("Registrar devolución").on(
                        "click",
                        js_handler="() => emit(props.row.id)",
                        handler=lambda e: ir_a_devolucion(e.args),
                    )
                    ui.button(icon="cancel").props(
                        "flat dense round color=negative " + _ocultar_si_no("puede_cancelar")
                    ).tooltip("Cancelar reserva").on(
                        "click",
                        js_handler="() => emit(props.row.id)",
                        handler=lambda e: confirmar_cancelacion(e.args),
                    )

    with ui.dialog() as dialogo, ui.card().classes("q-pa-md").style("min-width: 420px"):
        ui.label("Nueva reserva").classes("text-subtitle1 text-weight-medium")
        formulario = estado.formulario
        with ui.column().classes("w-full gap-2"):
            selector_usuario = (
                ui.select({}, label="Cliente")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "usuario")
            )
            selector_vehiculo = (
                ui.select({}, label="Vehículo disponible")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "vehiculo")
            )
            with ui.row().classes("w-full gap-2 no-wrap"):
                campo_fecha_inicio = (
                    ui.date_input("Fecha de inicio", value=date.today().isoformat())
                    .classes("col")
                    .bind_value(formulario, "fecha_inicio")
                )
                campo_fecha_fin = (
                    ui.date_input("Fecha de término", value=date.today().isoformat())
                    .classes("col")
                    .bind_value(formulario, "fecha_fin")
                )
            campo_observaciones = (
                ui.input("Observaciones").props("outlined dense").classes("w-full")
            ).bind_value(formulario, "observaciones")
            etiqueta_monto = ui.label("Monto estimado: $0 (0 días)").classes("text-weight-medium")

            selector_vehiculo.on_value_change(actualizar_monto_estimado)
            campo_fecha_inicio.on_value_change(actualizar_monto_estimado)
            campo_fecha_fin.on_value_change(actualizar_monto_estimado)
        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Crear reserva", on_click=crear_reserva, color="primary")

    await cargar()
