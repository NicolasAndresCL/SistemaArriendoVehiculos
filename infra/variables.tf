# Contrato de entrada del módulo.
#
# Toda variable lleva `type` y `description`: una variable sin tipo acepta
# cualquier cosa y falla en `apply` en vez de en `plan`, que es cuando todavía
# no se ha tocado nada.

variable "entorno" {
  description = "Entorno de despliegue: determina el namespace y las réplicas."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.entorno)
    error_message = "entorno debe ser uno de: dev, staging, prod."
  }
}

variable "namespace" {
  description = "Namespace de Kubernetes donde vive el sistema."
  type        = string
  default     = "arriendos"
}

variable "imagen" {
  description = "Imagen del contenedor con tag INMUTABLE (nunca 'latest')."
  type        = string

  validation {
    # Un tag `latest` hace que dos réplicas puedan acabar corriendo código
    # distinto sin que nadie pueda saber cuál.
    condition     = !endswith(var.imagen, ":latest")
    error_message = "La imagen no puede usar el tag 'latest': usar el SHA del commit."
  }
}

variable "replicas" {
  description = "Número de réplicas por componente."
  type        = number
  default     = 2

  validation {
    condition     = var.replicas >= 1 && var.replicas <= 10
    error_message = "replicas debe estar entre 1 y 10."
  }
}

variable "host_publico" {
  description = "Dominio público del sistema. Sin valor por defecto a propósito: que falte debe ser un fallo explícito."
  type        = string
}

variable "etiquetas" {
  description = "Etiquetas comunes aplicadas a todos los recursos."
  type        = map(string)
  default = {
    proyecto  = "sistema-arriendo-vehiculos"
    asignatura = "IEI-050"
    gestionado = "terraform"
  }
}
