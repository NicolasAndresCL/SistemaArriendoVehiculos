"""Tests del endpoint del catálogo de vehículos."""

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.vehiculos.models import Vehiculo

RUTA = "/api/v1/vehiculos/"


@pytest.fixture
def cliente_api_de_cliente(db, usuario_cliente):
    """`APIClient` autenticado como cliente, sin permisos de funcionario."""
    token, _ = Token.objects.get_or_create(user=usuario_cliente)
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return cliente


@pytest.mark.django_db
def test_listado_incluye_las_etiquetas_en_espanol(cliente_api, vehiculo):
    respuesta = cliente_api.get(RUTA)

    assert respuesta.status_code == 200
    fila = respuesta.data["results"][0]
    assert fila["categoria_display"] == "City car"
    assert fila["transmision_display"] == "Manual"
    assert fila["combustible_display"] == "Bencina"
    assert fila["estado_display"] == "Disponible"
    assert fila["descripcion"] == "Toyota Yaris 2022"


@pytest.mark.django_db
def test_crear_vehiculo_normaliza_la_patente(cliente_api):
    respuesta = cliente_api.post(
        RUTA,
        {
            "patente": " ffgg 33 ",
            "marca": "Kia",
            "modelo": "Rio",
            "anio": 2023,
            "categoria": Vehiculo.Categoria.SEDAN,
            "tarifa_diaria": 30000,
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["patente"] == "FFGG33"


@pytest.mark.django_db
def test_crear_vehiculo_con_patente_repetida_es_rechazado(cliente_api, vehiculo):
    respuesta = cliente_api.post(
        RUTA,
        {
            "patente": vehiculo.patente,
            "marca": "Otra",
            "modelo": "Cosa",
            "anio": 2023,
            "categoria": Vehiculo.Categoria.SUV,
            "tarifa_diaria": 30000,
        },
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.data["error"]["codigo"] == "peticion_invalida"


@pytest.mark.django_db
def test_filtros_de_estado_categoria_y_busqueda(cliente_api, vehiculo, vehiculo_en_mantenimiento):
    assert cliente_api.get(RUTA).data["count"] == 2
    assert cliente_api.get(f"{RUTA}?estado={Vehiculo.Estado.DISPONIBLE}").data["count"] == 1
    assert cliente_api.get(f"{RUTA}?categoria={Vehiculo.Categoria.SEDAN}").data["count"] == 1
    assert cliente_api.get(f"{RUTA}?buscar=yaris").data["count"] == 1
    assert cliente_api.get(f"{RUTA}?buscar=AABB").data["count"] == 1
    assert cliente_api.get(f"{RUTA}?buscar=nissan").data["count"] == 0


@pytest.mark.django_db
def test_un_cliente_puede_mirar_el_catalogo(cliente_api_de_cliente, vehiculo):
    assert cliente_api_de_cliente.get(RUTA).status_code == 200


@pytest.mark.django_db
def test_un_cliente_no_puede_dar_de_alta_un_vehiculo(cliente_api_de_cliente):
    respuesta = cliente_api_de_cliente.post(
        RUTA,
        {
            "patente": "ZZZZ99",
            "marca": "Fantasma",
            "modelo": "X",
            "anio": 2024,
            "categoria": Vehiculo.Categoria.SUV,
            "tarifa_diaria": 50000,
        },
        format="json",
    )

    assert respuesta.status_code == 403
    assert not Vehiculo.objects.filter(patente="ZZZZ99").exists()


@pytest.mark.django_db
def test_un_cliente_no_puede_editar_ni_borrar(cliente_api_de_cliente, vehiculo):
    assert (
        cliente_api_de_cliente.patch(
            f"{RUTA}{vehiculo.pk}/", {"tarifa_diaria": 1}, format="json"
        ).status_code
        == 403
    )
    assert cliente_api_de_cliente.delete(f"{RUTA}{vehiculo.pk}/").status_code == 403
    assert Vehiculo.objects.filter(pk=vehiculo.pk).exists()


@pytest.mark.django_db
def test_usuario_anonimo_no_ve_el_catalogo(cliente_api_anonimo):
    assert cliente_api_anonimo.get(RUTA).status_code == 401
