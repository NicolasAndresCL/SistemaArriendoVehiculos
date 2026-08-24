"""Página de administración de la flota de vehículos."""

from dataclasses import dataclass, field
from typing import Any

from nicegui import ui

from frontend.api_client import ErrorAPI, cliente_api, notificar_error
from frontend.layout import AppLayout
from frontend.theme import aplicar_tema
from frontend.utilidades import formatear_clp, formatear_kilometros

ETIQUETAS_CATEGORIA = {
    "CITYCAR": "City car",
    "SEDAN": "Sedán",
    "SUV": "SUV",
    "CAMIONETA": "Camioneta",
    "FURGON": "Furgón",
}
ETIQUETAS_TRANSMISION = {"MANUAL": "Manual", "AUTOMATICA": "Automática"}
ETIQUETAS_COMBUSTIBLE = {
    "BENCINA": "Bencina",
    "DIESEL": "Diésel",
    "HIBRIDO": "Híbrido",
    "ELECTRICO": "Eléctrico",
}
ETIQUETAS_ESTADO = {
    "DISPONIBLE": "Disponible",
    "ARRENDADO": "Arrendado",
    "MANTENIMIENTO": "En mantenimiento",
    "BAJA": "Dado de baja",
}
COLOR_ESTADO = {
    "DISPONIBLE": "primary",
    "ARRENDADO": "secondary",
    "MANTENIMIENTO": "negative",
    "BAJA": "negative",
}

COLUMNAS = [
    {"name": "patente", "label": "Patente", "field": "patente", "align": "left", "sortable": True},
    {"name": "vehiculo", "label": "Vehículo", "field": "vehiculo", "align": "left"},
    {"name": "categoria_display", "label": "Categoría", "field": "categoria_display"},
    {"name": "transmision_display", "label": "Transmisión", "field": "transmision_display"},
    {"name": "combustible_display", "label": "Combustible", "field": "combustible_display"},
    {"name": "tarifa", "label": "Tarifa diaria", "field": "tarifa", "align": "right"},
    {"name": "kilometraje", "label": "Kilometraje", "field": "kilometraje", "align": "right"},
    {"name": "estado_display", "label": "Estado", "field": "estado_display", "align": "center"},
    {"name": "acciones", "label": "Acciones", "field": "acciones", "align": "center"},
]


@dataclass
class FormularioVehiculo:
    """Estado del formulario de alta/edición de un vehículo."""

    id: int | None = None
    patente: str = ""
    marca: str = ""
    modelo: str = ""
    anio: int | None = None
    descripcion: str = ""
    categoria: str = "SEDAN"
    transmision: str = "MANUAL"
    combustible: str = "BENCINA"
    tarifa_diaria: float | None = None
    kilometraje: int | None = None
    estado: str = "DISPONIBLE"
    observaciones: str = ""

    def reiniciar(self) -> None:
        """Restaura todos los campos a sus valores por defecto."""
        self.id = None
        self.patente = ""
        self.marca = ""
        self.modelo = ""
        self.anio = None
        self.descripcion = ""
        self.categoria = "SEDAN"
        self.transmision = "MANUAL"
        self.combustible = "BENCINA"
        self.tarifa_diaria = None
        self.kilometraje = 0
        self.estado = "DISPONIBLE"
        self.observaciones = ""

    def cargar_desde(self, vehiculo: dict[str, Any]) -> None:
        """Copia los datos de un vehículo existente al formulario (modo edición)."""
        self.id = vehiculo.get("id")
        self.patente = vehiculo.get("patente", "")
        self.marca = vehiculo.get("marca", "")
        self.modelo = vehiculo.get("modelo", "")
        self.anio = vehiculo.get("anio")
        self.descripcion = vehiculo.get("descripcion", "") or ""
        self.categoria = vehiculo.get("categoria", "SEDAN")
        self.transmision = vehiculo.get("transmision", "MANUAL")
        self.combustible = vehiculo.get("combustible", "BENCINA")
        self.tarifa_diaria = vehiculo.get("tarifa_diaria")
        self.kilometraje = vehiculo.get("kilometraje")
        self.estado = vehiculo.get("estado", "DISPONIBLE")
        self.observaciones = vehiculo.get("observaciones", "") or ""


@dataclass
class EstadoVehiculos:
    """Datos cargados de la API y filtros activos de la página."""

    vehiculos: list[dict[str, Any]] = field(default_factory=list)
    formulario: FormularioVehiculo = field(default_factory=FormularioVehiculo)
    filtro_estado: str = ""
    filtro_categoria: str = ""
    filtro_busqueda: str = ""


async def pagina_vehiculos() -> None:
    """Construye la página de administración de vehículos."""
    aplicar_tema()
    AppLayout.current().show(ruta_activa="/vehiculos")

    estado = EstadoVehiculos()

    async def cargar() -> None:
        params: dict[str, str] = {}
        if estado.filtro_estado:
            params["estado"] = estado.filtro_estado
        if estado.filtro_categoria:
            params["categoria"] = estado.filtro_categoria
        if estado.filtro_busqueda:
            params["buscar"] = estado.filtro_busqueda
        try:
            estado.vehiculos = await cliente_api.listar("vehiculos/", params=params)
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        tabla.rows = [construir_fila(v) for v in estado.vehiculos]
        tabla.update()

    def construir_fila(vehiculo: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": vehiculo.get("id"),
            "patente": vehiculo.get("patente", ""),
            "vehiculo": f"{vehiculo.get('marca', '')} {vehiculo.get('modelo', '')} "
            f"({vehiculo.get('anio', '')})",
            "categoria_display": vehiculo.get("categoria_display", ""),
            "transmision_display": vehiculo.get("transmision_display", ""),
            "combustible_display": vehiculo.get("combustible_display", ""),
            "tarifa": formatear_clp(vehiculo.get("tarifa_diaria")),
            "kilometraje": formatear_kilometros(vehiculo.get("kilometraje")),
            "estado_display": vehiculo.get("estado_display", ""),
            "estado_color": COLOR_ESTADO.get(vehiculo.get("estado", ""), "primary"),
        }

    def abrir_nuevo() -> None:
        estado.formulario.reiniciar()
        dialogo_titulo.set_text("Nuevo vehículo")
        campo_patente.props(remove="disable")
        dialogo.open()

    def abrir_edicion(vehiculo_id: int) -> None:
        vehiculo = next((v for v in estado.vehiculos if v["id"] == vehiculo_id), None)
        if vehiculo is None:
            return
        estado.formulario.cargar_desde(vehiculo)
        dialogo_titulo.set_text("Editar vehículo")
        campo_patente.props("disable")
        dialogo.open()

    async def guardar() -> None:
        formulario = estado.formulario
        datos: dict[str, Any] = {
            "patente": formulario.patente,
            "marca": formulario.marca,
            "modelo": formulario.modelo,
            "anio": formulario.anio,
            "descripcion": formulario.descripcion,
            "categoria": formulario.categoria,
            "transmision": formulario.transmision,
            "combustible": formulario.combustible,
            "tarifa_diaria": formulario.tarifa_diaria,
            "kilometraje": formulario.kilometraje,
            "estado": formulario.estado,
            "observaciones": formulario.observaciones,
        }
        try:
            if formulario.id is None:
                await cliente_api.crear("vehiculos/", datos)
                ui.notify("Vehículo creado correctamente.", type="positive")
            else:
                await cliente_api.actualizar("vehiculos/", formulario.id, datos)
                ui.notify("Vehículo actualizado correctamente.", type="positive")
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        dialogo.close()
        await cargar()

    async def confirmar_eliminacion(vehiculo_id: int) -> None:
        vehiculo = next((v for v in estado.vehiculos if v["id"] == vehiculo_id), None)
        if vehiculo is None:
            return
        with ui.dialog() as confirmacion, ui.card():
            ui.label(f"¿Eliminar el vehículo {vehiculo.get('patente', '')}?")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=confirmacion.close).props("flat")

                async def eliminar() -> None:
                    try:
                        await cliente_api.eliminar("vehiculos/", vehiculo_id)
                        ui.notify("Vehículo eliminado.", type="positive")
                    except ErrorAPI as exc:
                        notificar_error(exc)
                    confirmacion.close()
                    await cargar()

                ui.button("Eliminar", on_click=eliminar, color="negative")
        confirmacion.open()

    with ui.row().classes("w-full items-center justify-between q-pa-md"):
        ui.label("Vehículos").classes("text-h6")
        ui.button("Nuevo vehículo", icon="add", on_click=abrir_nuevo)

    with ui.row().classes("w-full items-center gap-2 q-px-md q-pb-sm"):
        campo_buscar = (
            ui.input(placeholder="Buscar patente, marca o modelo...")
            .props("outlined dense clearable")
            .classes("col-4")
        )
        selector_estado = (
            ui.select({"": "Todos los estados", **ETIQUETAS_ESTADO}, value="")
            .props("outlined dense")
            .style("min-width: 220px")
        )
        selector_categoria = (
            ui.select({"": "Todas las categorías", **ETIQUETAS_CATEGORIA}, value="")
            .props("outlined dense")
            .style("min-width: 220px")
        )

    async def cambiar_busqueda() -> None:
        estado.filtro_busqueda = campo_buscar.value or ""
        await cargar()

    async def cambiar_estado_filtro() -> None:
        estado.filtro_estado = selector_estado.value or ""
        await cargar()

    async def cambiar_categoria_filtro() -> None:
        estado.filtro_categoria = selector_categoria.value or ""
        await cargar()

    campo_buscar.on("keydown.enter", cambiar_busqueda)
    campo_buscar.on("clear", cambiar_busqueda)
    selector_estado.on_value_change(cambiar_estado_filtro)
    selector_categoria.on_value_change(cambiar_categoria_filtro)

    with ui.column().classes("tarjeta-app q-mx-md q-mb-md q-pa-sm"):
        tabla = ui.table(columns=COLUMNAS, rows=[], row_key="id").classes("w-full")

        with tabla.add_slot("body-cell-estado_display"):
            with tabla.cell("estado_display"):
                ui.badge().props(':label="props.value" :color="props.row.estado_color"')

        with tabla.add_slot("body-cell-acciones"):
            with tabla.cell("acciones"):
                with ui.row().classes("gap-1 justify-center"):
                    ui.button(icon="edit").props("flat dense round color=primary").on(
                        "click",
                        js_handler="() => emit(props.row.id)",
                        handler=lambda e: abrir_edicion(e.args),
                    )
                    ui.button(icon="delete").props("flat dense round color=negative").on(
                        "click",
                        js_handler="() => emit(props.row.id)",
                        handler=lambda e: confirmar_eliminacion(e.args),
                    )

    with ui.dialog() as dialogo, ui.card().classes("q-pa-md").style("min-width: 480px"):
        dialogo_titulo = ui.label("Nuevo vehículo").classes("text-subtitle1 text-weight-medium")
        formulario = estado.formulario
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("w-full gap-2 no-wrap"):
                campo_patente = (
                    ui.input("Patente")
                    .props("outlined dense")
                    .classes("col")
                    .bind_value(formulario, "patente")
                )
                ui.number("Año", format="%.0f").props("outlined dense").classes("col").bind_value(
                    formulario, "anio"
                )
            with ui.row().classes("w-full gap-2 no-wrap"):
                ui.input("Marca").props("outlined dense").classes("col").bind_value(
                    formulario, "marca"
                )
                ui.input("Modelo").props("outlined dense").classes("col").bind_value(
                    formulario, "modelo"
                )
            ui.input("Descripción").props("outlined dense").classes("w-full").bind_value(
                formulario, "descripcion"
            )
            with ui.row().classes("w-full gap-2 no-wrap"):
                ui.select(ETIQUETAS_CATEGORIA, label="Categoría").props("outlined dense").classes(
                    "col"
                ).bind_value(formulario, "categoria")
                ui.select(ETIQUETAS_TRANSMISION, label="Transmisión").props(
                    "outlined dense"
                ).classes("col").bind_value(formulario, "transmision")
                ui.select(ETIQUETAS_COMBUSTIBLE, label="Combustible").props(
                    "outlined dense"
                ).classes("col").bind_value(formulario, "combustible")
            with ui.row().classes("w-full gap-2 no-wrap"):
                ui.number("Tarifa diaria (CLP)").props("outlined dense").classes("col").bind_value(
                    formulario, "tarifa_diaria"
                )
                ui.number("Kilometraje", format="%.0f").props("outlined dense").classes(
                    "col"
                ).bind_value(formulario, "kilometraje")
                ui.select(ETIQUETAS_ESTADO, label="Estado").props("outlined dense").classes(
                    "col"
                ).bind_value(formulario, "estado")
            ui.textarea("Observaciones").props("outlined dense").classes("w-full").bind_value(
                formulario, "observaciones"
            )
        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Guardar", on_click=guardar, color="primary")

    await cargar()
