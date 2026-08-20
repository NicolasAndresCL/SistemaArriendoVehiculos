"""Entorno de producción.

Objetivo explícito: `manage.py check --deploy --fail-level WARNING` sin un solo
warning. El CI lo verifica en un job aparte.
"""

from .base import *

DEBUG = False

# Sin valor por defecto a propósito: que falte la variable debe ser un fallo
# explícito al arrancar, no un "*" silencioso.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Un solo interruptor para todo el bloque HTTPS, de modo que el servicio pueda
# correr detrás de un proxy que aún no termina TLS sin tocar código.
SECURE_HTTPS = env.bool("SECURE_HTTPS", default=True)

SECURE_SSL_REDIRECT = SECURE_HTTPS
SESSION_COOKIE_SECURE = SECURE_HTTPS
CSRF_COOKIE_SECURE = SECURE_HTTPS
SECURE_HSTS_SECONDS = 31_536_000 if SECURE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HTTPS
SECURE_HSTS_PRELOAD = SECURE_HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
