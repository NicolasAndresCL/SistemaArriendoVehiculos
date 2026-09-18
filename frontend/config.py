"""Lectura de configuración de la interfaz desde variables de entorno.

Los valores se leen de ``.env`` (cargado por ``python-dotenv`` si está
presente) o directamente del entorno del proceso. Se definen valores por
defecto razonables para desarrollo local, coherentes con ``.env.example``
en la raíz del proyecto.
"""

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    _raiz_proyecto = Path(__file__).resolve().parent.parent
    load_dotenv(_raiz_proyecto / ".env")
except ImportError:
    # python-dotenv es opcional: si no está instalado, se asume que las
    # variables de entorno ya fueron exportadas por el sistema.
    pass


@dataclass(frozen=True)
class Configuracion:
    """Valores de configuración inmutables de la aplicación NiceGUI."""

    api_base_url: str
    storage_secret: str
    puerto: int


def cargar_configuracion() -> Configuracion:
    """Construye la configuración leyendo el entorno del proceso."""
    return Configuracion(
        api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
        storage_secret=os.getenv(
            "NICEGUI_STORAGE_SECRET", "clave-de-desarrollo-no-usar-en-produccion"
        ),
        # Configurable para que `scripts/verificar.ps1` levante la interfaz en
        # un puerto alternativo: el 8080 es también el de Jenkins, y una
        # instancia ajena escuchando ahí hace pasar (o fallar) la verificación
        # por motivos que no tienen que ver con el código.
        puerto=int(os.getenv("FRONTEND_PORT", "8080")),
    )


configuracion = cargar_configuracion()
