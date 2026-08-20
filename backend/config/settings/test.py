"""Entorno de tests.

Inyecta sus valores por defecto en `os.environ` ANTES de importar `base`, de
modo que la suite corra en un checkout limpio sin `.env` ni secretos. Cede el
paso a un `DATABASE_URL` real si el entorno lo trae.
"""

import os

os.environ.setdefault("SECRET_KEY", "clave-insegura-solo-para-tests")
os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")

from .base import *

DEBUG = False

# Hashing rápido: la suite crea muchos usuarios y no está probando PBKDF2.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 4},
    },
]

# Throttling desactivado, no borrado: DRF lanza ImproperlyConfigured si una
# vista referencia un scope que ya no existe en el diccionario.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"anon": None, "user": None, "login": None},
}
