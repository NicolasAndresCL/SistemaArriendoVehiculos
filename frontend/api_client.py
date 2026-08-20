"""Cliente HTTP contra la API REST del Sistema de Arriendo de Vehículos.

La interfaz nunca accede al ORM de Django: toda comunicación pasa por este
cliente, construido sobre ``httpx.AsyncClient``. También define el contrato
de error de la API (``ErrorAPI``) y la función de ayuda para notificarlo.
"""

from dataclasses import dataclass, field
from typing import Any

import httpx
from nicegui import app, ui

from frontend.config import configuracion

# Mensajes en español para los códigos de error documentados en el contrato
# de la API. Se usan como respaldo si el backend no entrega "mensaje", y
# también sirven de referencia rápida de qué códigos se manejan.
MENSAJES_ERROR: dict[str, str] = {
    "fechas_invalidas": "Las fechas ingresadas no son válidas.",
    "vehiculo_no_disponible": "El vehículo seleccionado no está disponible.",
    "licencia_vencida": "La licencia de conducir del cliente está vencida.",
    "reserva_no_pagable": "Esta reserva no admite un pago en este momento.",
    "pago_duplicado": "Ya existe un pago registrado para esta reserva.",
    "transicion_no_permitida": "Esa operación no es válida para el estado actual.",
    "devolucion_no_permitida": "No es posible registrar la devolución en este estado.",
    "kilometraje_invalido": "El kilometraje ingresado no es válido.",
    "peticion_invalida": "Los datos ingresados no son válidos.",
    "no_autenticado": "Debe iniciar sesión para continuar.",
    "sin_permiso": "No tiene permisos para realizar esta acción.",
    "no_encontrado": "El recurso solicitado no existe.",
    "demasiadas_peticiones": "Demasiadas peticiones. Intente nuevamente en unos minutos.",
    "api_inalcanzable": (
        "No fue posible conectar con la API. Verifique que el backend esté "
        "levantado con: python backend/manage.py runserver"
    ),
}


@dataclass
class ErrorAPI(Exception):
    """Excepción que representa un error devuelto por la API.

    Encapsula el contrato de error uniforme
    ``{"error": {"codigo", "mensaje", "detalle"}}`` que entrega el backend.
    """

    codigo: str
    mensaje: str
    detalle: dict[str, Any] = field(default_factory=dict)
    status: int = 0

    def __str__(self) -> str:
        return self.mensaje


def notificar_error(exc: ErrorAPI) -> None:
    """Muestra el mensaje de un ``ErrorAPI`` como notificación roja.

    Si el error es de autenticación (``no_autenticado``), además limpia el
    token guardado y redirige al login.
    """
    ui.notify(exc.mensaje, type="negative")
    if exc.codigo == "no_autenticado":
        app.storage.user.pop("token", None)
        app.storage.user.pop("usuario", None)
        ui.navigate.to("/login")


class ClienteAPI:
    """Cliente asíncrono contra la API REST v1 del backend."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or configuracion.api_base_url).rstrip("/")

    def _encabezados(self) -> dict[str, str]:
        token = app.storage.user.get("token")
        if token:
            return {"Authorization": f"Token {token}"}
        return {}

    async def _peticion(
        self,
        metodo: str,
        ruta: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Ejecuta una petición HTTP y traduce errores al contrato de error."""
        url = f"{self._base_url}/{ruta.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as cliente:
                respuesta = await cliente.request(
                    metodo,
                    url,
                    params=params,
                    json=json,
                    headers=self._encabezados(),
                )
        except httpx.ConnectError as exc:
            raise ErrorAPI(
                codigo="api_inalcanzable",
                mensaje=MENSAJES_ERROR["api_inalcanzable"],
                status=0,
            ) from exc

        if respuesta.status_code == 204:
            return None

        if respuesta.is_success:
            if not respuesta.content:
                return None
            return respuesta.json()

        self._lanzar_error(respuesta)
        return None  # inalcanzable: _lanzar_error siempre lanza

    def _lanzar_error(self, respuesta: httpx.Response) -> None:
        """Interpreta una respuesta de error y lanza ``ErrorAPI``."""
        try:
            cuerpo = respuesta.json()
            error = cuerpo.get("error", {})
            codigo = error.get("codigo", "error_desconocido")
            mensaje = error.get(
                "mensaje", MENSAJES_ERROR.get(codigo, "Ocurrió un error inesperado.")
            )
            detalle = error.get("detalle", {})
        except ValueError:
            codigo = "error_desconocido"
            mensaje = "Ocurrió un error inesperado al comunicarse con la API."
            detalle = {}
        raise ErrorAPI(
            codigo=codigo,
            mensaje=mensaje,
            detalle=detalle,
            status=respuesta.status_code,
        )

    # -- Autenticación -----------------------------------------------------

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Autentica contra la API y devuelve ``{"token", "usuario"}``."""
        return await self._peticion(
            "POST", "auth/login/", json={"email": email, "password": password}
        )

    async def logout(self) -> None:
        """Invalida el token actual en el backend."""
        await self._peticion("POST", "auth/logout/")

    async def yo(self) -> dict[str, Any]:
        """Obtiene los datos del usuario autenticado."""
        return await self._peticion("GET", "auth/yo/")

    # -- CRUD genérico -------------------------------------------------------

    async def obtener(self, ruta: str, params: dict[str, Any] | None = None) -> Any:
        """Realiza un GET a ``ruta`` y devuelve el cuerpo íntegro de la respuesta."""
        return await self._peticion("GET", ruta, params=params)

    async def listar(self, ruta: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Realiza un GET a un listado paginado y devuelve solo ``results``."""
        cuerpo = await self._peticion("GET", ruta, params=params)
        if cuerpo is None:
            return []
        return cuerpo.get("results", [])

    async def crear(self, ruta: str, datos: dict[str, Any]) -> Any:
        """Realiza un POST para crear un recurso en ``ruta``."""
        return await self._peticion("POST", ruta, json=datos)

    async def actualizar(self, ruta: str, id_: int | str, datos: dict[str, Any]) -> Any:
        """Realiza un PATCH sobre ``ruta/id_/``."""
        return await self._peticion("PATCH", f"{ruta.rstrip('/')}/{id_}/", json=datos)

    async def eliminar(self, ruta: str, id_: int | str) -> None:
        """Realiza un DELETE sobre ``ruta/id_/``."""
        await self._peticion("DELETE", f"{ruta.rstrip('/')}/{id_}/")

    async def accion(
        self, ruta: str, id_: int | str, nombre: str, datos: dict[str, Any] | None = None
    ) -> Any:
        """Invoca una acción personalizada ``POST ruta/id_/nombre/``."""
        return await self._peticion("POST", f"{ruta.rstrip('/')}/{id_}/{nombre}/", json=datos or {})


cliente_api = ClienteAPI()
