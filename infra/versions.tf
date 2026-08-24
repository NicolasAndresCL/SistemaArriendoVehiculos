# Versiones y estado remoto.
#
# Fijar versiones no es burocracia: sin restricción, un proveedor publica una
# versión mayor y el `apply` de mañana se comporta distinto al de hoy sin que
# nadie haya tocado el código.

terraform {
  required_version = "~> 1.9"

  required_providers {
    # `~>` (restricción pesimista): acepta parches y menores, bloquea el salto
    # a la siguiente mayor, que es donde viven los cambios incompatibles.
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # El estado es el activo crítico: un tfstate local no se puede compartir, no
  # se puede bloquear y guarda los secretos EN CLARO.
  #
  # Los valores se pasan con `-backend-config` para no fijar el bucket en el
  # repositorio:
  #   terraform init -backend-config=backend.hcl
  backend "s3" {
    key     = "arriendos/terraform.tfstate"
    encrypt = true

    # Bloqueo nativo de S3. El bloqueo por tabla DynamoDB (`dynamodb_table`)
    # está deprecado y se eliminará en una versión futura: en proyectos nuevos
    # no debe usarse. Sin bloqueo, dos `apply` simultáneos corrompen el estado
    # — y eso pasa la primera vez que dos personas trabajan el mismo día.
    use_lockfile = true
  }
}
