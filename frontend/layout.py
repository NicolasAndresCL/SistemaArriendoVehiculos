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
        self.avatar = None
        # Ítems del menú indexados por ruta, para poder marcar el activo sin
        # reconstruir el drawer en cada navegación.
        self.items_navegacion: dict[str, ui.item] = {}
        self.ruta_activa = ""
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
            with ui.row().classes("items-center gap-3"):
                ui.icon("directions_car", size="26px")
                ui.label("Sistema de Arriendo de Vehículos").classes(
                    "text-base font-semibold marca-app"
                )
            with ui.row().classes("items-center gap-3"):
                # Avatar con iniciales: identifica la sesión de un vistazo sin
                # depender solo del nombre, que se trunca en pantallas angostas.
                self.avatar = ui.label("").classes("avatar-sesion")
                self.etiqueta_usuario = ui.label("").classes("usuario-sesion")
                ui.button(icon="logout", on_click=self._cerrar_sesion).props(
                    "flat round dense color=white"
                ).tooltip("Cerrar sesión")

        with ui.left_drawer().classes("text-white") as barra_lateral:
            self.drawer = barra_lateral
            ui.label("Gestión").classes("nav-seccion")
            with ui.list().props("padding").classes("w-full"):
                for ruta, etiqueta, icono in ELEMENTOS_NAVEGACION:
                    # `partial` y no una lambda con argumento por defecto: el
                    # elemento clicable es el `ui.item` completo, de modo que
                    # el clic sobre el ícono o sobre el texto navega igual.
                    with ui.item(on_click=partial(ui.navigate.to, ruta)).classes(
                        "nav-item"
                    ) as elemento:
                        self.items_navegacion[ruta] = elemento
                        with ui.item_section().props("avatar"):
                            ui.icon(icono, color="white").props("size=20px")
                        with ui.item_section():
                            ui.label(etiqueta).classes("text-sm")

        self.show()

    def marcar_activo(self, ruta: str) -> None:
        """Resalta en el menú la sección que se está viendo."""
        self.ruta_activa = ruta
        for ruta_item, elemento in self.items_navegacion.items():
            if ruta_item == ruta:
                elemento.classes(add="nav-item-activo")
            else:
                elemento.classes(remove="nav-item-activo")

    def show(self, ruta_activa: str | None = None) -> None:
        """Muestra header y drawer y refresca el nombre del usuario conectado."""
        usuario = app.storage.user.get("usuario") or {}
        self.sesion.nombre = usuario.get("nombre_completo") or usuario.get("email", "")
        self.sesion.email = usuario.get("email", "")
        if self.etiqueta_usuario is not None:
            self.etiqueta_usuario.set_text(self.sesion.nombre)
        if self.avatar is not None:
            self.avatar.set_text(_iniciales(self.sesion.nombre))
        if ruta_activa is not None:
            self.marcar_activo(ruta_activa)
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


def _iniciales(nombre: str) -> str:
    """Devuelve hasta dos iniciales en mayúscula para el avatar de la cabecera."""
    partes = [parte for parte in nombre.split() if parte]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def hay_sesion_activa() -> bool:
    """Indica si existe un token de autenticación guardado."""
    return bool(app.storage.user.get("token"))
