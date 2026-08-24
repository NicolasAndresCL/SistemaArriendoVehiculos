"""Página de inicio de sesión.

Es una ruta de ``ui.sub_pages`` (``/login``), no una ``@ui.page`` aparte,
para que el estado del cliente y el header/drawer compartidos se manejen
con el mismo mecanismo que el resto de la aplicación.
"""

from dataclasses import dataclass

from nicegui import app, ui

from frontend.api_client import ErrorAPI, cliente_api, notificar_error
from frontend.layout import AppLayout
from frontend.theme import aplicar_tema


@dataclass
class EstadoLogin:
    """Estado del formulario de inicio de sesión."""

    email: str = "admin@estacionamiento.cl"
    password: str = ""
    cargando: bool = False


def pagina_login() -> None:
    """Construye la página de login y oculta el header/drawer compartidos."""
    aplicar_tema()
    AppLayout.current().hide()

    estado = EstadoLogin()

    async def enviar() -> None:
        if estado.cargando:
            return
        if not estado.email or not estado.password:
            ui.notify("Ingrese correo y contraseña.", type="warning")
            return
        estado.cargando = True
        boton_ingresar.props("loading")
        try:
            respuesta = await cliente_api.login(estado.email, estado.password)
        except ErrorAPI as exc:
            notificar_error(exc)
        else:
            app.storage.user["token"] = respuesta["token"]
            app.storage.user["usuario"] = respuesta["usuario"]
            ui.navigate.to("/")
        finally:
            estado.cargando = False
            boton_ingresar.props(remove="loading")

    with ui.column().classes("franja-login"):
        with ui.card().classes("tarjeta-login items-stretch"):
            with ui.column().classes("items-center w-full gap-2 q-mb-lg"):
                with ui.element("div").classes("logo-login"):
                    ui.icon("directions_car").props("size=28px")
                ui.label("Sistema de Arriendo de Vehículos").classes("titulo-login")
                ui.label("Inicie sesión para continuar").classes("subtitulo-login")

            campo_email = (
                ui.input("Correo electrónico")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(estado, "email")
            )
            campo_email.on("keydown.enter", enviar)

            campo_password = (
                ui.input("Contraseña", password=True, password_toggle_button=True)
                .props("outlined dense")
                .classes("w-full")
                .bind_value(estado, "password")
            )
            campo_password.on("keydown.enter", enviar)

            boton_ingresar = (
                ui.button("Ingresar", on_click=enviar)
                .props("unelevated size=md")
                .classes("w-full q-mt-md")
            )

            ui.separator().classes("q-my-md")
            with ui.column().classes("w-full gap-1 credenciales-demo items-center"):
                ui.label("Credenciales de demostración")
                ui.label("admin@estacionamiento.cl / 1234").classes("credencial")
