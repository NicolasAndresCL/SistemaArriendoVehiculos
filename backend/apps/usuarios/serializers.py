"""Serializers de usuarios."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ValidationErrorDjango
from django.utils import timezone
from rest_framework import serializers

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """Representación de un usuario para la API.

    La contraseña es de solo escritura: entra al crear o actualizar, nunca sale
    en una respuesta.
    """

    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    nombre_completo = serializers.CharField(read_only=True)
    rol_display = serializers.CharField(source="get_rol_display", read_only=True)
    licencia_vigente = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "password",
            "rut",
            "nombre",
            "apellido",
            "nombre_completo",
            "telefono",
            "rol",
            "rol_display",
            "licencia_numero",
            "licencia_vencimiento",
            "licencia_vigente",
            "is_active",
            "is_staff",
            "fecha_registro",
        ]
        read_only_fields = ["id", "fecha_registro"]

    def get_licencia_vigente(self, obj: Usuario) -> bool:
        return obj.licencia_vigente_al(timezone.localdate())

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except ValidationErrorDjango as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict) -> dict:
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "La contraseña es obligatoria al crear un usuario."}
            )
        return attrs

    def create(self, validated_data: dict) -> Usuario:
        password = validated_data.pop("password")
        return Usuario.objects.create_user(password=password, **validated_data)

    def update(self, instance: Usuario, validated_data: dict) -> Usuario:
        # La contraseña no se puede asignar como un campo más: hay que hashearla.
        password = validated_data.pop("password", None)
        usuario = super().update(instance, validated_data)
        if password:
            usuario.set_password(password)
            usuario.save(update_fields=["password"])
        return usuario


class LoginSerializer(serializers.Serializer):
    """Credenciales de ingreso: email y contraseña."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
