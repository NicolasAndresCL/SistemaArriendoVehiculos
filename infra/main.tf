# Infraestructura del Sistema de Arriendo de Vehículos.
#
# Alcance: lo que debe existir ANTES de que los pods arranquen — el namespace,
# su política de seguridad, el almacenamiento y los secretos generados. Los
# Deployments viven en `deploy/k8s/` como manifiestos versionados: describirlos
# también aquí sería mantener dos fuentes de verdad para lo mismo.

provider "kubernetes" {
  # Sin credenciales en el código: se toman del kubeconfig del entorno o del
  # credential store del CI.
  config_path = "~/.kube/config"
}

locals {
  etiquetas = merge(var.etiquetas, {
    entorno = var.entorno
  })
}

resource "kubernetes_namespace" "arriendos" {
  metadata {
    name = var.namespace
    labels = merge(local.etiquetas, {
      # Pod Security Admission en `restricted`: rechaza pods que corran como
      # root o que escalen privilegios. Reemplazó a PodSecurityPolicy.
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
    })
  }
}

# Clave de firma generada aquí y nunca escrita a mano: una contraseña inventada
# y pegada en una variable termina copiada en un chat o en un commit.
resource "random_password" "secret_key" {
  length  = 64
  special = true
}

resource "random_password" "nicegui_storage" {
  length  = 64
  special = true
}

resource "kubernetes_secret" "arriendos" {
  metadata {
    name      = "arriendos-secretos"
    namespace = kubernetes_namespace.arriendos.metadata[0].name
    labels    = local.etiquetas
  }

  # ADVERTENCIA: estos valores quedan EN CLARO dentro del tfstate. `sensitive`
  # oculta la salida en el log del plan, pero no cifra el estado. De ahí que el
  # backend deba estar cifrado y con acceso restringido: quien lea el bucket,
  # lee estos secretos.
  data = {
    SECRET_KEY             = random_password.secret_key.result
    NICEGUI_STORAGE_SECRET = random_password.nicegui_storage.result
  }

  type = "Opaque"
}

resource "kubernetes_config_map" "arriendos" {
  metadata {
    name      = "arriendos-config"
    namespace = kubernetes_namespace.arriendos.metadata[0].name
    labels    = local.etiquetas
  }

  data = {
    DJANGO_SETTINGS_MODULE = "config.settings.prod"
    DATABASE_URL           = "sqlite:////app/datos/db.sqlite3"
    ALLOWED_HOSTS          = "${var.host_publico},backend"
    CSRF_TRUSTED_ORIGINS   = "https://${var.host_publico}"
    SECURE_HTTPS           = "True"
    API_BASE_URL           = "http://backend:8000/api/v1"
  }
}

resource "kubernetes_persistent_volume_claim" "datos" {
  metadata {
    name      = "arriendos-datos"
    namespace = kubernetes_namespace.arriendos.metadata[0].name
    labels    = local.etiquetas
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "1Gi"
      }
    }
  }

  # El volumen guarda la base de datos: destruirlo por un renombrado o un
  # `destroy` distraído es irreversible.
  lifecycle {
    prevent_destroy = true
  }

  # Sin esto, Terraform espera indefinidamente a que un PVC con
  # `WaitForFirstConsumer` se enlace, cuando el primer consumidor todavía no
  # existe porque los Deployments los aplica Kustomize después.
  wait_until_bound = false
}
