"""Vistas del catálogo de vehículos."""

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.api.permissions import EsOperadorOSoloLectura

from .models import Vehiculo
from .serializers import VehiculoSerializer


class VehiculoViewSet(viewsets.ModelViewSet):
    """CRUD de la flota.

    Cualquier usuario autenticado puede consultar el catálogo; solo un
    funcionario puede darlo de alta, modificarlo o retirarlo.
    """

    serializer_class = VehiculoSerializer
    queryset = Vehiculo.objects.all()
    permission_classes = [IsAuthenticated, EsOperadorOSoloLectura]

    def get_queryset(self):
        queryset = super().get_queryset()
        parametros = self.request.query_params

        if estado := parametros.get("estado"):
            queryset = queryset.filter(estado=estado)
        if categoria := parametros.get("categoria"):
            queryset = queryset.filter(categoria=categoria)
        if buscar := parametros.get("buscar"):
            queryset = queryset.filter(
                Q(patente__icontains=buscar)
                | Q(marca__icontains=buscar)
                | Q(modelo__icontains=buscar)
            )
        return queryset
