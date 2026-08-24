# Infraestructura (Terraform)

Crea lo que debe existir **antes** de que los pods arranquen: el namespace con
su política de seguridad, la configuración, los secretos generados y el
volumen de datos.

Los `Deployment`, `Service` e `Ingress` **no** están aquí: viven en
[`deploy/k8s/`](../deploy/k8s/) como manifiestos versionados. Describirlos en
ambos sitios sería mantener dos fuentes de verdad para lo mismo.

## Qué crea

| Recurso | Para qué |
|---|---|
| `kubernetes_namespace` | Aísla el sistema y aplica Pod Security Admission `restricted` |
| `random_password` (×2) | Genera `SECRET_KEY` y `NICEGUI_STORAGE_SECRET` sin que nadie las escriba a mano |
| `kubernetes_secret` | Entrega esas claves a los pods |
| `kubernetes_config_map` | Configuración no sensible (hosts, URL de la API, HTTPS) |
| `kubernetes_persistent_volume_claim` | Almacenamiento de la base SQLite, con `prevent_destroy` |

## Uso

```bash
# 1. Inicializar con el backend remoto (bucket fuera del repo)
terraform init -backend-config=backend.hcl

# 2. Revisar SIEMPRE el plan antes de aplicar: es el único momento en que se
#    ve qué se va a destruir. Leer entero las líneas "destroy and then create".
terraform plan -out=tfplan \
  -var="entorno=prod" \
  -var="host_publico=arriendos.example.cl" \
  -var="imagen=registro/sistema-arriendo:a1d0925"

# 3. Aplicar exactamente el plan revisado, no uno recalculado
terraform apply tfplan
```

`backend.hcl` (no versionado):

```hcl
bucket = "miorg-tfstate"
region = "us-east-1"
```

## Reglas de operación

- **Nunca editar recursos a mano en la consola web ni con `kubectl edit`.**
  Produce *drift*: el estado deja de reflejar la realidad y el próximo `apply`
  deshace el cambio manual sin avisar.
- **`apply` con aprobación humana**, nunca automático sobre producción.
- **`.terraform.lock.hcl` se commitea**; `.tfstate` y `.terraform/`, jamás.
- El estado guarda los secretos **en claro**: el bucket va cifrado, versionado
  y con acceso restringido.

## Advertencia sobre el alcance

Este módulo asume un clúster ya existente y accesible vía `~/.kube/config`.
Crear el clúster mismo (VPC, nodos, IAM) queda fuera: es específico del
proveedor y excede lo que la asignatura evalúa. La estructura está lista para
añadirlo como un módulo hermano en `modules/`.
