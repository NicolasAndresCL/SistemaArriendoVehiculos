"""Modelo de usuario del sistema.

El ingreso es por email y contraseña —no por nombre de usuario—, así que el
proyecto define un usuario propio con `USERNAME_FIELD = "email"` en lugar de
usar el `User` de Django.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UsuarioManager(BaseUserManager):
    """Manager que crea usuarios identificados por email."""

    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra):
        if not email:
            raise ValueError("El email es obligatorio.")
        usuario = self.model(email=self.normalize_email(email), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Un superusuario debe tener is_staff e is_superuser en True.")
        return self.create_user(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Cliente o funcionario del sistema de arriendos."""

    class Rol(models.TextChoices):
        CLIENTE = "CLIENTE", "Cliente"
        OPERADOR = "OPERADOR", "Operador"

    email = models.EmailField("correo electrónico", unique=True)
    rut = models.CharField("RUT", max_length=12, unique=True)
    nombre = models.CharField(max_length=60)
    apellido = models.CharField(max_length=60)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.CLIENTE)

    licencia_numero = models.CharField("número de licencia", max_length=20, blank=True)
    licencia_vencimiento = models.DateField("vencimiento de licencia", null=True, blank=True)

    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("es funcionario", default=False)
    fecha_registro = models.DateTimeField("fecha de registro", default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["rut", "nombre", "apellido"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["apellido", "nombre"]

    def __str__(self) -> str:
        return f"{self.nombre} {self.apellido} <{self.email}>"

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()

    def licencia_vigente_al(self, fecha) -> bool:
        """¿Tiene licencia de conducir válida en esa fecha?

        Sin fecha de vencimiento registrada se considera no vigente: es más
        seguro rechazar el arriendo que entregar un vehículo sin verificar.
        """
        if self.licencia_vencimiento is None:
            return False
        return self.licencia_vencimiento >= fecha
