"""Página de administración de usuarios (clientes y operadores)."""

from dataclasses import dataclass, field
from typing import Any

from nicegui import ui

from frontend.api_client import ErrorAPI, cliente_api, notificar_error
from frontend.layout import AppLayout
from frontend.theme import aplicar_tema
from frontend.utilidades import formatear_fecha

ETIQUETAS_ROL = {"CLIENTE": "Cliente", "OPERADOR": "Operador"}

COLUMNAS = [
    {"name": "email", "label": "Correo", "field": "email", "align": "left", "sortable": True},
    {"name": "rut", "label": "RUT", "field": "rut", "align": "left"},
    {
        "name": "nombre_completo",
        "label": "Nombre",
        "field": "nombre_completo",
        "align": "left",
        "sortable": True,
    },
    {"name": "telefono", "label": "Teléfono", "field": "telefono", "align": "left"},
    {"name": "rol_display", "label": "Rol", "field": "rol_display", "align": "left"},
    {"name": "licencia", "label": "Licencia", "field": "licencia", "align": "left"},
    {"name": "activo", "label": "Activo", "field": "activo", "align": "center"},
    {"name": "acciones", "label": "Acciones", "field": "acciones", "align": "center"},
]


@dataclass
class FormularioUsuario:
    """Estado del formulario de alta/edición de un usuario."""

    id: int | None = None
    email: str = ""
    password: str = ""
    rut: str = ""
    nombre: str = ""
    apellido: str = ""
    telefono: str = ""
    rol: str = "CLIENTE"
    licencia_numero: str = ""
    licencia_vencimiento: str | None = None
    is_active: bool = True

    def reiniciar(self) -> None:
        """Restaura todos los campos a sus valores por defecto."""
        self.id = None
        self.email = ""
        self.password = ""
        self.rut = ""
        self.nombre = ""
        self.apellido = ""
        self.telefono = ""
        self.rol = "CLIENTE"
        self.licencia_numero = ""
        self.licencia_vencimiento = None
        self.is_active = True

    def cargar_desde(self, usuario: dict[str, Any]) -> None:
        """Copia los datos de un usuario existente al formulario (modo edición)."""
        self.id = usuario.get("id")
        self.email = usuario.get("email", "")
        self.password = ""
        self.rut = usuario.get("rut", "")
        self.nombre = usuario.get("nombre", "")
        self.apellido = usuario.get("apellido", "")
        self.telefono = usuario.get("telefono", "") or ""
        self.rol = usuario.get("rol", "CLIENTE")
        self.licencia_numero = usuario.get("licencia_numero", "") or ""
        self.licencia_vencimiento = usuario.get("licencia_vencimiento")
        self.is_active = bool(usuario.get("is_active", True))


@dataclass
class EstadoUsuarios:
    """Datos cargados de la API y formulario activo del diálogo."""

    usuarios: list[dict[str, Any]] = field(default_factory=list)
    formulario: FormularioUsuario = field(default_factory=FormularioUsuario)


async def pagina_usuarios() -> None:
    """Construye la página de administración de usuarios."""
    aplicar_tema()
    AppLayout.current().show(ruta_activa="/usuarios")

    estado = EstadoUsuarios()

    async def cargar() -> None:
        try:
            estado.usuarios = await cliente_api.listar("usuarios/")
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        refrescar_filas()

    def refrescar_filas() -> None:
        tabla.rows = [construir_fila(u) for u in estado.usuarios]
        tabla.update()

    def construir_fila(usuario: dict[str, Any]) -> dict[str, Any]:
        licencia = usuario.get("licencia_numero") or ""
        if licencia:
            licencia = f"{licencia} (vence {formatear_fecha(usuario.get('licencia_vencimiento'))})"
        return {
            "id": usuario.get("id"),
            "email": usuario.get("email", ""),
            "rut": usuario.get("rut", ""),
            "nombre_completo": usuario.get("nombre_completo", ""),
            "telefono": usuario.get("telefono", "") or "-",
            "rol_display": usuario.get("rol_display", ""),
            "licencia": licencia or "-",
            "licencia_vigente": bool(usuario.get("licencia_vigente")),
            "tiene_licencia": bool(licencia),
            "activo": usuario.get("is_active", True),
        }

    def abrir_nuevo() -> None:
        estado.formulario.reiniciar()
        campo_password.set_visibility(True)
        dialogo_titulo.set_text("Nuevo usuario")
        dialogo.open()

    def abrir_edicion(usuario_id: int) -> None:
        usuario = next((u for u in estado.usuarios if u["id"] == usuario_id), None)
        if usuario is None:
            return
        estado.formulario.cargar_desde(usuario)
        campo_password.set_visibility(False)
        dialogo_titulo.set_text("Editar usuario")
        dialogo.open()

    async def guardar() -> None:
        formulario = estado.formulario
        datos: dict[str, Any] = {
            "email": formulario.email,
            "rut": formulario.rut,
            "nombre": formulario.nombre,
            "apellido": formulario.apellido,
            "telefono": formulario.telefono,
            "rol": formulario.rol,
            "licencia_numero": formulario.licencia_numero,
            "licencia_vencimiento": formulario.licencia_vencimiento,
            "is_active": formulario.is_active,
        }
        try:
            if formulario.id is None:
                datos["password"] = formulario.password
                await cliente_api.crear("usuarios/", datos)
                ui.notify("Usuario creado correctamente.", type="positive")
            else:
                await cliente_api.actualizar("usuarios/", formulario.id, datos)
                ui.notify("Usuario actualizado correctamente.", type="positive")
        except ErrorAPI as exc:
            notificar_error(exc)
            return
        dialogo.close()
        await cargar()

    async def confirmar_eliminacion(usuario_id: int) -> None:
        usuario = next((u for u in estado.usuarios if u["id"] == usuario_id), None)
        if usuario is None:
            return
        with ui.dialog() as confirmacion, ui.card():
            ui.label(f"¿Eliminar al usuario {usuario.get('email', '')}?")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=confirmacion.close).props("flat")

                async def eliminar() -> None:
                    try:
                        await cliente_api.eliminar("usuarios/", usuario_id)
                        ui.notify("Usuario eliminado.", type="positive")
                    except ErrorAPI as exc:
                        notificar_error(exc)
                    confirmacion.close()
                    await cargar()

                ui.button("Eliminar", on_click=eliminar, color="negative")
        confirmacion.open()

    with ui.row().classes("w-full items-center justify-between q-pa-md"):
        ui.label("Usuarios").classes("text-h6")
        with ui.row().classes("items-center gap-2"):
            campo_busqueda = ui.input(placeholder="Buscar...").props("outlined dense clearable")
            ui.button("Nuevo usuario", icon="add", on_click=abrir_nuevo)

    with ui.column().classes("tarjeta-app q-mx-md q-mb-md q-pa-sm"):
        tabla = ui.table(columns=COLUMNAS, rows=[], row_key="id").classes("w-full")
        campo_busqueda.bind_value(tabla, "filter")

        with tabla.add_slot("body-cell-licencia"):
            with tabla.cell("licencia"):
                ui.element("div").props(
                    ':class="props.row.tiene_licencia && !props.row.licencia_vigente '
                    "? 'text-negative text-weight-medium' : ''\" "
                    ':innerHTML="props.value"'
                )

        with tabla.add_slot("body-cell-activo"):
            with tabla.cell("activo"):
                ui.badge().props(
                    ":label=\"props.value ? 'Activo' : 'Inactivo'\" "
                    ":color=\"props.value ? 'primary' : 'negative'\""
                )

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

    with ui.dialog() as dialogo, ui.card().classes("q-pa-md").style("min-width: 420px"):
        dialogo_titulo = ui.label("Nuevo usuario").classes("text-subtitle1 text-weight-medium")
        formulario = estado.formulario
        with ui.column().classes("w-full gap-2"):
            ui.input("Correo electrónico").props("outlined dense").classes("w-full").bind_value(
                formulario, "email"
            )
            campo_password = (
                ui.input("Contraseña", password=True, password_toggle_button=True)
                .props("outlined dense")
                .classes("w-full")
                .bind_value(formulario, "password")
            )
            with ui.row().classes("w-full gap-2 no-wrap"):
                ui.input("RUT").props("outlined dense").classes("col").bind_value(formulario, "rut")
                ui.input("Teléfono").props("outlined dense").classes("col").bind_value(
                    formulario, "telefono"
                )
            with ui.row().classes("w-full gap-2 no-wrap"):
                ui.input("Nombre").props("outlined dense").classes("col").bind_value(
                    formulario, "nombre"
                )
                ui.input("Apellido").props("outlined dense").classes("col").bind_value(
                    formulario, "apellido"
                )
            ui.select(ETIQUETAS_ROL, label="Rol").props("outlined dense").classes(
                "w-full"
            ).bind_value(formulario, "rol")
            with ui.row().classes("w-full gap-2 no-wrap"):
                ui.input("Número de licencia").props("outlined dense").classes("col").bind_value(
                    formulario, "licencia_numero"
                )
                ui.input("Vencimiento licencia").props("outlined dense type=date").classes(
                    "col"
                ).bind_value(formulario, "licencia_vencimiento")
            ui.switch("Usuario activo").bind_value(formulario, "is_active")
        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Guardar", on_click=guardar, color="primary")

    await cargar()
