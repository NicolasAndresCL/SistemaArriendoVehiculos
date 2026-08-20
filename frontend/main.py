"""Punto de entrada de la interfaz NiceGUI del Sistema de Arriendo de Vehículos.

Esta aplicación es una SPA construida con ``ui.sub_pages``: una única
``@ui.page('/')`` construye el layout compartido (header y drawer) y
enruta el resto de las vistas del lado del cliente, sin recargas de
página. Toda la comunicación con los datos ocurre por HTTP contra la API
REST de Django (ver ``frontend/api_client.py``); esta capa nunca importa
Django ni accede al ORM.
"""

import sys
from pathlib import Path

# Permite arrancar tanto con `python frontend/main.py` como con
# `python -m frontend.main`: en el primer caso sys.path apunta a frontend/ y
# los imports absolutos `frontend.*` no resolverían sin esto.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from nicegui import app, ui  # noqa: E402
from nicegui.page_arguments import PageArguments  # noqa: E402

from frontend.config import configuracion  # noqa: E402
from frontend.layout import AppLayout, hay_sesion_activa  # noqa: E402
from frontend.paginas.devoluciones import pagina_devoluciones  # noqa: E402
from frontend.paginas.login import pagina_login  # noqa: E402
from frontend.paginas.pagos import pagina_pagos  # noqa: E402
from frontend.paginas.panel import pagina_panel  # noqa: E402
from frontend.paginas.reservas import pagina_reservas  # noqa: E402
from frontend.paginas.usuarios import pagina_usuarios  # noqa: E402
from frontend.paginas.vehiculos import pagina_vehiculos  # noqa: E402
from frontend.theme import aplicar_tema  # noqa: E402

RUTA_ESTATICOS = Path(__file__).parent / "static"
app.add_static_files("/static", str(RUTA_ESTATICOS))


async def _panel() -> None:
    """Envoltorio del panel que exige sesión activa antes de renderizar."""
    if not hay_sesion_activa():
        ui.navigate.to("/login")
        return
    await pagina_panel()


async def _usuarios() -> None:
    """Envoltorio de usuarios que exige sesión activa antes de renderizar."""
    if not hay_sesion_activa():
        ui.navigate.to("/login")
        return
    await pagina_usuarios()


async def _vehiculos() -> None:
    """Envoltorio de vehículos que exige sesión activa antes de renderizar."""
    if not hay_sesion_activa():
        ui.navigate.to("/login")
        return
    await pagina_vehiculos()


async def _reservas() -> None:
    """Envoltorio de reservas que exige sesión activa antes de renderizar."""
    if not hay_sesion_activa():
        ui.navigate.to("/login")
        return
    await pagina_reservas()


async def _pagos(args: PageArguments) -> None:
    """Envoltorio de pagos que exige sesión activa antes de renderizar."""
    if not hay_sesion_activa():
        ui.navigate.to("/login")
        return
    await pagina_pagos(args)


async def _devoluciones(args: PageArguments) -> None:
    """Envoltorio de devoluciones que exige sesión activa antes de renderizar."""
    if not hay_sesion_activa():
        ui.navigate.to("/login")
        return
    await pagina_devoluciones(args)


def raiz() -> None:
    """Página raíz: construye el layout compartido y enruta las sub-páginas.

    Se entrega a ``ui.run`` como página raíz, de modo que NiceGUI la sirva
    también como respaldo para el resto de las URL (mecanismo de 404 de
    ``ui.sub_pages``), por lo que no se necesita una ruta comodín
    adicional.
    """
    aplicar_tema()
    AppLayout.current().construir()

    ui.sub_pages(
        {
            "/login": pagina_login,
            "/": _panel,
            "/usuarios": _usuarios,
            "/vehiculos": _vehiculos,
            "/reservas": _reservas,
            "/pagos": _pagos,
            "/devoluciones": _devoluciones,
        }
    )


if __name__ in {"__main__", "__mp_main__"}:
    # `raiz` se pasa como página raíz y no se declara con `@ui.page("/")`:
    # solo así NiceGUI la usa como respaldo de las URL que no coinciden con
    # ninguna ruta de servidor. Sin esto, recargar el navegador en /reservas
    # devuelve un 404 en vez de dejar que `ui.sub_pages` resuelva la vista.
    ui.run(
        raiz,
        title="Sistema de Arriendo de Vehículos",
        show=False,
        port=8080,
        storage_secret=configuracion.storage_secret,
    )
