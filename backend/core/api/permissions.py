"""Permisos reutilizables de la API.

`IsAuthenticated` solo responde "¿quién eres?", no "¿esto es tuyo?". Hacen falta
las dos mitades —filtro de queryset y permiso de objeto— o queda un agujero: el
listado seguiría devolviendo lo ajeno aunque el detalle esté protegido.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class EsOperadorOSoloLectura(BasePermission):
    """Lectura para cualquier autenticado, escritura solo para funcionarios.

    Es el patrón del catálogo de vehículos: un cliente puede mirar la flota,
    pero no dar de alta un auto.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


class EsDuenoUOperador(BasePermission):
    """Acceso a un objeto solo para su dueño o para un funcionario.

    El atributo que identifica al dueño se declara en la vista con
    `campo_dueno` (por defecto `usuario`).
    """

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        campo = getattr(view, "campo_dueno", "usuario")
        dueno = obj
        for parte in campo.split("__"):
            dueno = getattr(dueno, parte, None)
            if dueno is None:
                return False
        return dueno == request.user


class PorDuenoMixin:
    """Filtra el listado al dueño cuando quien consulta no es funcionario.

    Sin este filtro, el permiso de objeto protege el detalle por id pero el
    listado sigue exponiendo lo ajeno.
    """

    campo_dueno = "usuario"

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario = self.request.user
        if usuario.is_staff:
            return queryset
        return queryset.filter(**{self.campo_dueno: usuario})
