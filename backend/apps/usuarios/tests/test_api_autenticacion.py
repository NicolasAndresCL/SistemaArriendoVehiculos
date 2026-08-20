"""Tests de los endpoints de autenticación y del CRUD de usuarios."""

import datetime as dt

import pytest
from rest_framework.authtoken.models import Token

from apps.usuarios.models import Usuario
from conftest import HOY

RUTA_LOGIN = "/api/v1/auth/login/"
RUTA_USUARIOS = "/api/v1/usuarios/"


@pytest.fixture
def cliente_api_de_cliente(db, usuario_cliente):
    """`APIClient` autenticado como cliente, no como funcionario."""
    from rest_framework.test import APIClient

    token, _ = Token.objects.get_or_create(user=usuario_cliente)
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return cliente


@pytest.mark.django_db
def test_login_con_credenciales_correctas_devuelve_token(cliente_api_anonimo, usuario_cliente):
    respuesta = cliente_api_anonimo.post(
        RUTA_LOGIN,
        {"email": usuario_cliente.email, "password": "clave-segura"},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.data["token"]
    assert respuesta.data["usuario"]["email"] == usuario_cliente.email
    # La contraseña jamás vuelve en la respuesta.
    assert "password" not in respuesta.data["usuario"]


@pytest.mark.django_db
def test_login_con_contrasena_incorrecta_devuelve_401(cliente_api_anonimo, usuario_cliente):
    respuesta = cliente_api_anonimo.post(
        RUTA_LOGIN, {"email": usuario_cliente.email, "password": "otra"}, format="json"
    )

    assert respuesta.status_code == 401
    assert respuesta.data["error"]["codigo"] == "credenciales_invalidas"


@pytest.mark.django_db
def test_login_con_usuario_inexistente_devuelve_401(cliente_api_anonimo):
    respuesta = cliente_api_anonimo.post(
        RUTA_LOGIN, {"email": "nadie@correo.cl", "password": "x"}, format="json"
    )

    assert respuesta.status_code == 401


@pytest.mark.django_db
def test_login_sin_email_devuelve_400(cliente_api_anonimo):
    respuesta = cliente_api_anonimo.post(RUTA_LOGIN, {"password": "x"}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["error"]["codigo"] == "peticion_invalida"


@pytest.mark.django_db
def test_yo_devuelve_el_usuario_conectado(cliente_api, operador):
    respuesta = cliente_api.get("/api/v1/auth/yo/")

    assert respuesta.status_code == 200
    assert respuesta.data["email"] == operador.email
    assert respuesta.data["is_staff"] is True


@pytest.mark.django_db
def test_logout_invalida_el_token(cliente_api, operador):
    assert cliente_api.post("/api/v1/auth/logout/").status_code == 204
    assert not Token.objects.filter(user=operador).exists()
    # El mismo cliente, con el token ya borrado, deja de tener acceso.
    assert cliente_api.get("/api/v1/auth/yo/").status_code == 401


@pytest.mark.django_db
def test_crear_usuario_hashea_la_contrasena(cliente_api):
    respuesta = cliente_api.post(
        RUTA_USUARIOS,
        {
            "email": "nuevo@correo.cl",
            "password": "clave-larga-y-segura",
            "rut": "55.555.555-5",
            "nombre": "Elena",
            "apellido": "Vidal",
        },
        format="json",
    )

    assert respuesta.status_code == 201
    creado = Usuario.objects.get(email="nuevo@correo.cl")
    assert creado.password != "clave-larga-y-segura"
    assert creado.check_password("clave-larga-y-segura")


@pytest.mark.django_db
def test_crear_usuario_sin_contrasena_es_rechazado(cliente_api):
    respuesta = cliente_api.post(
        RUTA_USUARIOS,
        {"email": "sinclave@correo.cl", "rut": "66.666.666-6", "nombre": "F", "apellido": "G"},
        format="json",
    )

    assert respuesta.status_code == 400
    assert "password" in respuesta.data["error"]["detalle"]


@pytest.mark.django_db
def test_crear_usuario_con_contrasena_debil_es_rechazado(cliente_api, settings):
    settings.AUTH_PASSWORD_VALIDATORS = [
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {"min_length": 12},
        }
    ]

    respuesta = cliente_api.post(
        RUTA_USUARIOS,
        {
            "email": "debil@correo.cl",
            "password": "1234",
            "rut": "77.777.777-7",
            "nombre": "H",
            "apellido": "I",
        },
        format="json",
    )

    assert respuesta.status_code == 400
    assert "password" in respuesta.data["error"]["detalle"]


@pytest.mark.django_db
def test_actualizar_contrasena_la_vuelve_a_hashear(cliente_api, usuario_cliente):
    respuesta = cliente_api.patch(
        f"{RUTA_USUARIOS}{usuario_cliente.pk}/",
        {"password": "otra-clave-distinta"},
        format="json",
    )

    assert respuesta.status_code == 200
    usuario_cliente.refresh_from_db()
    assert usuario_cliente.check_password("otra-clave-distinta")


@pytest.mark.django_db
def test_actualizar_sin_contrasena_no_toca_la_existente(cliente_api, usuario_cliente):
    hash_previo = usuario_cliente.password

    respuesta = cliente_api.patch(
        f"{RUTA_USUARIOS}{usuario_cliente.pk}/", {"telefono": "+56 9 1111 1111"}, format="json"
    )

    assert respuesta.status_code == 200
    usuario_cliente.refresh_from_db()
    assert usuario_cliente.password == hash_previo


@pytest.mark.django_db
def test_licencia_vigente_se_calcula_en_la_respuesta(
    cliente_api, usuario_cliente, usuario_licencia_vencida
):
    respuesta = cliente_api.get(f"{RUTA_USUARIOS}{usuario_cliente.pk}/")
    assert respuesta.data["licencia_vigente"] is True

    respuesta = cliente_api.get(f"{RUTA_USUARIOS}{usuario_licencia_vencida.pk}/")
    assert respuesta.data["licencia_vigente"] is False


@pytest.mark.django_db
def test_filtros_de_busqueda_y_rol(cliente_api, usuario_cliente, usuario_sin_licencia):
    assert cliente_api.get(f"{RUTA_USUARIOS}?buscar=Pérez").data["count"] == 1
    assert cliente_api.get(f"{RUTA_USUARIOS}?buscar=11.111").data["count"] == 1
    assert cliente_api.get(f"{RUTA_USUARIOS}?buscar=nadie").data["count"] == 0
    # Los tres usuarios de la prueba nacen con rol CLIENTE: el operador lo es
    # por `is_staff`, que es un permiso, no un rol de negocio.
    assert cliente_api.get(f"{RUTA_USUARIOS}?rol={Usuario.Rol.CLIENTE}").data["count"] == 3
    assert cliente_api.get(f"{RUTA_USUARIOS}?rol={Usuario.Rol.OPERADOR}").data["count"] == 0


@pytest.mark.django_db
def test_un_cliente_solo_se_ve_a_si_mismo(cliente_api_de_cliente, usuario_cliente, operador):
    respuesta = cliente_api_de_cliente.get(RUTA_USUARIOS)

    assert respuesta.data["count"] == 1
    assert respuesta.data["results"][0]["email"] == usuario_cliente.email


@pytest.mark.django_db
def test_un_cliente_no_puede_crear_usuarios(cliente_api_de_cliente):
    respuesta = cliente_api_de_cliente.post(
        RUTA_USUARIOS,
        {
            "email": "intruso@correo.cl",
            "password": "clave-larga-y-segura",
            "rut": "88.888.888-8",
            "nombre": "J",
            "apellido": "K",
        },
        format="json",
    )

    assert respuesta.status_code == 403
    assert respuesta.data["error"]["codigo"] == "sin_permiso"


@pytest.mark.django_db
def test_un_cliente_no_puede_borrar_a_otro(cliente_api_de_cliente, operador):
    respuesta = cliente_api_de_cliente.delete(f"{RUTA_USUARIOS}{operador.pk}/")

    # 403 por el permiso de creación/borrado, y jamás un borrado efectivo.
    assert respuesta.status_code in (403, 404)
    assert Usuario.objects.filter(pk=operador.pk).exists()


@pytest.mark.django_db
def test_usuario_anonimo_no_accede_al_listado(cliente_api_anonimo):
    respuesta = cliente_api_anonimo.get(RUTA_USUARIOS)

    assert respuesta.status_code == 401
    assert respuesta.data["error"]["codigo"] == "no_autenticado"


@pytest.mark.django_db
def test_fecha_ancla_de_las_fixtures_es_estable():
    """La suite no depende del reloj real: HOY es una fecha fija."""
    assert HOY == dt.date(2026, 1, 1)
