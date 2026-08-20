"""Vistas de usuarios y autenticación."""

from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.api.permissions import EsOperadorOSoloLectura

from .models import Usuario
from .serializers import LoginSerializer, UsuarioSerializer


class ThrottleLogin(ScopedRateThrottle):
    """Límite propio para el login: es el endpoint que se ataca por fuerza bruta."""

    scope = "login"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([ThrottleLogin])
def login(request: Request) -> Response:
    """Autentica por email y contraseña, y devuelve el token de la sesión."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    usuario = authenticate(
        request,
        username=serializer.validated_data["email"],
        password=serializer.validated_data["password"],
    )
    if usuario is None:
        return Response(
            {
                "error": {
                    "codigo": "credenciales_invalidas",
                    "mensaje": "El correo o la contraseña no son correctos.",
                    "detalle": {},
                }
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=usuario)
    return Response({"token": token.key, "usuario": UsuarioSerializer(usuario).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    """Invalida el token de la sesión actual."""
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def yo(request: Request) -> Response:
    """Datos del usuario conectado."""
    return Response(UsuarioSerializer(request.user).data)


class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD de usuarios.

    Un cliente solo se ve a sí mismo; un funcionario ve y administra a todos.
    """

    serializer_class = UsuarioSerializer
    queryset = Usuario.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            return queryset.filter(pk=self.request.user.pk)

        parametros = self.request.query_params
        if rol := parametros.get("rol"):
            queryset = queryset.filter(rol=rol)
        if buscar := parametros.get("buscar"):
            queryset = queryset.filter(
                Q(nombre__icontains=buscar)
                | Q(apellido__icontains=buscar)
                | Q(email__icontains=buscar)
                | Q(rut__icontains=buscar)
            )
        return queryset

    def get_permissions(self):
        # Crear y borrar usuarios es tarea de funcionarios; editarse a uno
        # mismo, no. El queryset ya limita a quién puede tocar un cliente.
        if self.action in ("create", "destroy"):
            return [IsAuthenticated(), EsOperadorOSoloLectura()]
        return super().get_permissions()
