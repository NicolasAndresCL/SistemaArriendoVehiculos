"""Rutas raíz del proyecto."""

from django.contrib import admin
from django.urls import include, path

from core.api.views import salud

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", salud, name="salud"),
    path("api/v1/", include("config.api_urls")),
]
