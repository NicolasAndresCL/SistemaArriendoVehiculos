"""Entorno de desarrollo local.

Inyecta sus propios valores por defecto antes de importar `base`, para que
`manage.py runserver` funcione en un checkout limpio sin `.env`.
"""

import os

os.environ.setdefault("SECRET_KEY", "clave-insegura-solo-para-desarrollo-local")

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# La contraseña por defecto del sistema es "1234" (requisito del enunciado).
# Los validadores completos siguen activos en producción; relajarlos aquí es
# lo que permite reproducir esa credencial desde la propia interfaz.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 4},
    },
]

CORS_ALLOW_ALL_ORIGINS = True
