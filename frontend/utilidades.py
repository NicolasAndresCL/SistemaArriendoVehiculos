"""Funciones de formateo compartidas por las páginas de la interfaz.

Se centralizan aquí para no repetir la misma lógica de formato de montos y
fechas en cada página (paneles, tablas y diálogos).
"""

from datetime import date, datetime


def formatear_clp(monto: float | int | str | None) -> str:
    """Formatea un monto como pesos chilenos: ``$1.234.567``."""
    if monto in (None, ""):
        return "$0"
    try:
        valor = round(float(monto))
    except (TypeError, ValueError):
        return "$0"
    texto = f"{abs(valor):,}".replace(",", ".")
    signo = "-" if valor < 0 else ""
    return f"{signo}${texto}"


def formatear_fecha(valor: str | date | datetime | None) -> str:
    """Formatea una fecha (ISO ``aaaa-mm-dd`` o ``datetime``) como ``dd-mm-aaaa``."""
    if not valor:
        return "-"
    if isinstance(valor, datetime):
        return valor.strftime("%d-%m-%Y")
    if isinstance(valor, date):
        return valor.strftime("%d-%m-%Y")
    texto = str(valor)
    # Admite tanto "aaaa-mm-dd" como marcas de tiempo ISO con hora.
    parte_fecha = texto[:10]
    try:
        return datetime.strptime(parte_fecha, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return texto


def hoy_iso() -> str:
    """Fecha actual en formato ``aaaa-mm-dd``, para valores por defecto de ``ui.date``."""
    return date.today().isoformat()


def formatear_kilometros(valor: float | int | str | None) -> str:
    """Formatea un kilometraje con separador de miles: ``89.020 km``."""
    if valor in (None, ""):
        return "0 km"
    try:
        entero = round(float(valor))
    except (TypeError, ValueError):
        return "0 km"
    return f"{entero:,}".replace(",", ".") + " km"
