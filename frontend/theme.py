"""Paleta de colores y estilos globales de la interfaz.

Paleta fija a azul, rojo y blanco por requisito del cliente. No existe
modo oscuro: la aplicación se diseña con esta paleta única.
"""

from pathlib import Path

from nicegui import ui

RUTA_CSS = Path(__file__).parent / "static" / "css" / "app.css"

AZUL = "#0D3B8C"
AZUL_CLARO = "#1565C0"
ROJO = "#C62828"
BLANCO = "#FFFFFF"
TEXTO = "#0B2A5B"

# Colores de apoyo para chips de estado, expuestos para reutilizar en
# las páginas sin repetir códigos hexadecimales.
COLOR_ESTADO_POSITIVO = AZUL
COLOR_ESTADO_NEUTRO = AZUL_CLARO
COLOR_ESTADO_ADVERSO = ROJO


def aplicar_tema() -> None:
    """Configura los colores de NiceGUI y carga las hojas de estilo.

    Debe llamarse una vez por página, al inicio de su función generadora,
    antes de construir cualquier elemento visual.
    """
    ui.colors(
        primary=AZUL,
        secondary=AZUL_CLARO,
        accent=ROJO,
        negative=ROJO,
        positive=AZUL,
        dark="#0B2A5B",
    )
    # La hoja propia se pide con la fecha de modificación como versión: sin
    # ella el navegador sirve la copia en caché y los cambios de estilo no se
    # ven hasta forzar una recarga dura.
    version = int(RUTA_CSS.stat().st_mtime) if RUTA_CSS.exists() else 0
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
        '&display=swap" rel="stylesheet">'
        f'<link rel="stylesheet" href="/static/css/app.css?v={version}">'
    )
