"""Diseño compartido de la aplicación: cabecera, menú lateral y sesión.

Define ``AppLayout``, la clase que construye header y drawer -elementos que
NiceGUI exige crear fuera de ``ui.sub_pages``- y que cada página usa para
mostrarse u ocultarse. La instancia vive en ``app.storage.client`` (no en
una variable global) y se recupera con el classmethod ``AppLayout.current()``.
"""

from dataclasses import dataclass
from functools import partial

from nicegui import app, ui

from frontend.api_client import ErrorAPI, cliente_api

# Elementos de navegación del drawer: (ruta, etiqueta, ícono material).
ELEMENTOS_NAVEGACION = [
    ("/", "Panel", "dashboard"),
    ("/usuarios", "Usuarios", "people"),
    ("/vehiculos", "Vehículos", "directions_car"),
    ("/reservas", "Reservas", "event"),
    ("/pagos", "Pagos", "payments"),
    ("/devoluciones", "Devoluciones", "assignment_return"),
]


@dataclass
class EstadoSesion:
    """Datos del usuario autenticado que se muestran en la cabecera."""

    nombre: str = ""
    email: str = ""


class AppLayout:
    """Cabecera y menú lateral compartidos por todas las páginas normales."""

    def __init__(self) -> None:
        self.header = None
        self.drawer = None
        self.etiqueta_usuario = None
        self.sesion = EstadoSesion()

    @classmethod
    def current(cls) -> "AppLayout":
        """Devuelve la instancia única de este cliente, creándola si falta."""
        if "layout" not in app.storage.client:
            app.storage.client["layout"] = cls()
        return app.storage.client["layout"]

    def construir(self) -> None:
        """Crea header y drawer. Debe llamarse una sola vez, en la página raíz."""
        with ui.header().classes("items-center justify-between") as encabezado:
            self.header = encabezado
            with ui.row().classes("items-center gap-2"):
                ui.icon("directions_car", size="28px")
                ui.label("Sistema de Arriendo de Vehículos").classes("text-lg font-semibold")
            with ui.row().classes("items-center gap-4"):
                self.etiqueta_usuario = ui.label("")
                ui.button(icon="logout", on_click=self._cerrar_sesion).props(
                    "flat round color=white"
                ).tooltip("Cerrar sesión")

        with ui.left_drawer().classes("bg-primary text-white") as barra_lateral:
            self.drawer = barra_lateral
            with ui.list().props("padding").classes("w-full"):
                for ruta, etiqueta, icono in ELEMENTOS_NAVEGACION:
                    # `partial` y no una lambda con argumento por defecto: el
                    # elemento clicable es el `ui.item` completo, de modo que
                    # el clic sobre el ícono o sobre el texto navega igual.
                    with ui.item(on_click=partial(ui.navigate.to, ruta)).classes("rounded-borders"):
                        with ui.item_section().props("avatar"):
                            ui.icon(icono, color="white")
                        with ui.item_section():
                            ui.label(etiqueta)

        self.show()

    def show(self) -> None:
        """Muestra header y drawer y refresca el nombre del usuario conectado."""
        usuario = app.storage.user.get("usuario") or {}
        self.sesion.nombre = usuario.get("nombre_completo") or usuario.get("email", "")
        self.sesion.email = usuario.get("email", "")
        if self.etiqueta_usuario is not None:
            self.etiqueta_usuario.set_text(self.sesion.nombre)
        if self.header is not None:
            self.header.set_visibility(True)
        if self.drawer is not None:
            self.drawer.set_visibility(True)
            self.drawer.show()

    def hide(self) -> None:
        """Oculta header y drawer (usado en la página de login)."""
        if self.header is not None:
            self.header.set_visibility(False)
        if self.drawer is not None:
            self.drawer.set_visibility(False)
            self.drawer.hide()

    async def _cerrar_sesion(self) -> None:
        """Cierra la sesión contra la API y limpia el estado local."""
        try:
            await cliente_api.logout()
        except ErrorAPI:
            # Si el token ya era inválido en el servidor, igual se limpia
            # la sesión local: el usuario debe volver a autenticarse.
            pass
        app.storage.user.pop("token", None)
        app.storage.user.pop("usuario", None)
        ui.navigate.to("/login")


def hay_sesion_activa() -> bool:
    """Indica si existe un token de autenticación guardado."""
    return bool(app.storage.user.get("token"))
