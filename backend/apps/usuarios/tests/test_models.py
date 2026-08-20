"""Tests del modelo `Usuario` y su manager."""

from datetime import date

import pytest

from apps.usuarios.models import Usuario

# ---------------------------------------------------------------------------
# UsuarioManager
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_user_crea_usuario_identificado_por_email():
    usuario = Usuario.objects.create_user(
        email="nueva@correo.cl",
        password="clave-segura",
        rut="55.555.555-5",
        nombre="Elena",
        apellido="Vidal",
    )
    assert usuario.pk is not None
    assert usuario.email == "nueva@correo.cl"
    assert usuario.check_password("clave-segura")


@pytest.mark.django_db
def test_create_user_sin_email_lanza_value_error():
    with pytest.raises(ValueError):
        Usuario.objects.create_user(
            email="",
            password="clave-segura",
            rut="66.666.666-6",
            nombre="Sin",
            apellido="Email",
        )


@pytest.mark.django_db
def test_create_superuser_con_is_staff_false_lanza_value_error():
    with pytest.raises(ValueError):
        Usuario.objects.create_superuser(
            email="admin@correo.cl",
            password="clave-segura",
            rut="77.777.777-7",
            nombre="Admin",
            apellido="Root",
            is_staff=False,
        )


# ---------------------------------------------------------------------------
# Usuario.nombre_completo
# ---------------------------------------------------------------------------


def test_nombre_completo_concatena_nombre_y_apellido():
    usuario = Usuario(nombre="Juan", apellido="Torres")
    assert usuario.nombre_completo == "Juan Torres"


# ---------------------------------------------------------------------------
# Usuario.licencia_vigente_al
# ---------------------------------------------------------------------------


def test_licencia_vigente_al_con_licencia_vigente():
    usuario = Usuario(licencia_vencimiento=date(2026, 12, 31))
    assert usuario.licencia_vigente_al(date(2026, 1, 1)) is True


def test_licencia_vigente_al_con_licencia_vencida():
    usuario = Usuario(licencia_vencimiento=date(2026, 1, 1))
    assert usuario.licencia_vigente_al(date(2026, 6, 1)) is False


def test_licencia_vigente_al_sin_fecha_registrada_es_falso():
    usuario = Usuario(licencia_vencimiento=None)
    assert usuario.licencia_vigente_al(date(2026, 6, 1)) is False
