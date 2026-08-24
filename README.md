# Sistema de Arriendo de Vehículos

[![CI](https://github.com/NicolasAndresCL/SistemaArriendoVehiculos/actions/workflows/ci.yml/badge.svg)](https://github.com/NicolasAndresCL/SistemaArriendoVehiculos/actions/workflows/ci.yml)

Sistema de gestión de arriendo de vehículos desarrollado para la asignatura **Diseño de
Software (IEI-050)** de la Universidad Santo Tomás. Cubre el ciclo completo del negocio:
registro de usuarios, catálogo de vehículos, reservas, pagos y devoluciones.

---

## Arquitectura

```
┌──────────────────────┐        HTTP + Token         ┌──────────────────────────┐
│   NiceGUI  :8080     │ ──────────────────────────► │  Django + DRF  :8000     │
│   frontend/          │ ◄────────────────────────── │  backend/                │
│   solo presentación  │      JSON /api/v1/...       │  reglas de negocio       │
└──────────────────────┘                             └───────────┬──────────────┘
                                                                 │ ORM
                                                          ┌──────▼───────┐
                                                          │  db.sqlite3  │
                                                          └──────────────┘
```

Son **dos procesos separados**. La interfaz nunca toca el ORM: consume la API igual que lo
haría cualquier otro cliente. Eso mantiene las reglas de negocio en un solo lugar y permite
probarlas sin levantar un servidor.

### Organización del backend

Las cinco entidades del enunciado se agrupan en **tres apps**, según su límite de agregado y
no una app por modelo:

| App | Modelos | Por qué |
|-----|---------|---------|
| `usuarios` | `Usuario` | Django exige que el modelo de `AUTH_USER_MODEL` viva en su propia app |
| `vehiculos` | `Vehiculo` | Catálogo con ciclo de vida propio, independiente de los arriendos |
| `arriendos` | `Reserva`, `Pago`, `Devolucion` | Un solo agregado: un pago o una devolución no existen sin su reserva |

Capas dentro de cada app:

- **`models.py`** — estructura y restricciones de integridad (incluidas las de base de datos).
- **`services.py`** — reglas de negocio. Es el único lugar donde se cambia el estado de una
  reserva. **Lanza excepciones de dominio**; no arma respuestas HTTP.
- **`serializers.py`** — validación de la forma de los datos; delega en los servicios.
- **`views.py`** — enrutado y permisos.

---

## Máquina de estados de la reserva

```
                    registrar_pago()          registrar_retiro()
   ┌───────────┐   ────────────────►  ┌────────────┐  ─────────────►  ┌──────────┐
   │ PENDIENTE │                      │ CONFIRMADA │                  │ EN_CURSO │
   └─────┬─────┘                      └──────┬─────┘                  └────┬─────┘
         │                                   │                             │
         │            cancelar_reserva()     │                             │
         └───────────────┬───────────────────┴─────────────────────────────┘
                         ▼                                                 │
                   ┌───────────┐                     registrar_devolucion() │
                   │ CANCELADA │                                            ▼
                   └───────────┘                                    ┌────────────┐
                                                                    │ FINALIZADA │
                                                                    └────────────┘
```

Las transiciones son **acciones explícitas de la API** (`POST /reservas/{id}/retirar/`,
`POST /reservas/{id}/cancelar/`), no un `PATCH` sobre el campo `estado`: cada una tiene reglas
propias y efectos sobre el estado del vehículo que una actualización genérica no podría
validar. Por eso `estado` y `monto_estimado` son campos de solo lectura en el serializer.

Efecto sobre el vehículo:

| Transición | Vehículo queda en |
|------------|-------------------|
| Retiro | `ARRENDADO` |
| Devolución sin daños | `DISPONIBLE`, con el kilometraje actualizado |
| Devolución con daños o marcada para taller | `MANTENIMIENTO` |
| Cancelación de una reserva ya retirada | `DISPONIBLE` |

---

## Reglas de negocio

Todas viven en `backend/apps/arriendos/services.py` y se manifiestan como excepciones de
dominio (`backend/core/exceptions.py`):

| Código | HTTP | Regla |
|--------|------|-------|
| `fechas_invalidas` | 400 | La fecha de término debe ser posterior a la de inicio |
| `vehiculo_no_disponible` | 409 | El vehículo no está disponible, o ya tiene una reserva activa que se traslapa con el período |
| `licencia_vencida` | 409 | El cliente no tiene licencia de conducir vigente al inicio del arriendo |
| `reserva_no_pagable` | 409 | Solo una reserva pendiente admite el registro de un pago |
| `pago_duplicado` | 409 | La reserva ya tiene un pago registrado |
| `transicion_no_permitida` | 409 | El retiro o la cancelación no proceden desde el estado actual |
| `devolucion_no_permitida` | 409 | Solo una reserva confirmada o en curso se devuelve, y solo una vez |
| `kilometraje_invalido` | 400 | El kilometraje de devolución no puede ser menor al del vehículo |

Se usa **409 y no 400** en los conflictos de estado a propósito: la petición está bien
formada, choca con la situación actual del sistema. Es "alguien se te adelantó", no "te
equivocaste al pedir".

**Cálculos**: días facturables = `max(1, fecha_fin - fecha_inicio)`; monto = días × tarifa
diaria; recargo por atraso = días de atraso × tarifa diaria × 1,5, más el cargo por daños que
tase el operador.

### Contrato de error

Todos los errores de la API, propios y de DRF, salen con la misma forma:

```json
{"error": {"codigo": "vehiculo_no_disponible",
           "mensaje": "El vehículo ZBCD11 ya tiene una reserva activa en ese período.",
           "detalle": {"patente": "ZBCD11"}}}
```

El `codigo` es el identificador estable que consume la interfaz; el `mensaje` en español puede
cambiar sin romper a nadie.

---

## Puesta en marcha

Requiere **Python 3.12 o superior** (probado en 3.14).

```powershell
cd SistemaArriendoVehiculos

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Base de datos y datos de demostración
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py seed_demo
```

Luego, para levantar backend y frontend con un clic, ejecutar `iniciar.bat` (doble clic o
`.\iniciar.bat` desde PowerShell). Abre una ventana para cada proceso; cerrar la ventana
detiene ese proceso.

Alternativamente, en **dos terminales**:

```powershell
# Terminal 1 — API
.\.venv\Scripts\python.exe backend\manage.py runserver 8000

# Terminal 2 — interfaz
.\.venv\Scripts\python.exe frontend\main.py
```

La interfaz queda en <http://localhost:8080> y la API en <http://localhost:8000/api/v1/>.

### Credenciales por defecto

| Correo | Contraseña | Rol |
|--------|-----------|-----|
| `admin@estacionamiento.cl` | `1234` | Operador (administrador) |

Los clientes de demostración usan la misma contraseña. Uno de ellos tiene la licencia vencida
a propósito, para que la regla que rechaza esa reserva se pueda ver funcionando.

> La contraseña `1234` es un requisito del enunciado. Los validadores de contraseña de Django
> están relajados en `dev` y `test` para permitirla, y **completos en `prod`**.

### Regenerar los datos de demostración

`seed_demo` es idempotente: usa `get_or_create`, así que **no modifica los registros que ya
existen**. Si los datos de demostración cambian en el código (por ejemplo, los nombres de los
clientes) y tu base ya estaba creada, seguirás viendo los valores antiguos. Para partir de
cero, borrar la base y volver a generarla:

```powershell
Remove-Item db.sqlite3
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py seed_demo
```

`db.sqlite3` no se versiona precisamente por esto: es desechable y se reconstruye con esos
dos comandos.

---

## API

Base: `http://localhost:8000/api/v1/`. Autenticación por token de DRF:
`Authorization: Token <token>`. Los listados vienen paginados
(`{"count", "next", "previous", "results"}`).

| Método y ruta | Qué hace |
|---------------|----------|
| `POST /auth/login/` | Ingreso con `{"email", "password"}` → `{"token", "usuario"}` |
| `POST /auth/logout/` | Invalida el token |
| `GET /auth/yo/` | Datos del usuario conectado |
| `GET POST /usuarios/` · `GET PUT PATCH DELETE /usuarios/{id}/` | Registro de usuarios |
| `GET POST /vehiculos/` · detalle | Catálogo. Filtros: `?estado=`, `?categoria=`, `?buscar=` |
| `GET POST /reservas/` · detalle | Reservas. Filtros: `?estado=`, `?vehiculo=` |
| `POST /reservas/{id}/retirar/` | Entrega del vehículo al cliente |
| `POST /reservas/{id}/cancelar/` | Anulación, con `{"motivo"}` opcional |
| `GET POST /pagos/` | Registro de pagos (sin borrado: un pago se anula, no se elimina) |
| `GET POST /devoluciones/` | Cierre del arriendo |
| `GET /healthz/` | Sonda de vida, sin autenticación |

### Permisos

Los permisos se aplican en **las dos mitades**: filtro de queryset y permiso de objeto. Sin la
primera, el listado seguiría devolviendo lo ajeno aunque el detalle estuviera protegido.

- Un cliente ve y gestiona **solo lo suyo**; un operador (`is_staff`) ve todo.
- `perform_create` fuerza el dueño desde el usuario autenticado: mandar `{"usuario": 7}` en el
  cuerpo no permite reservar a nombre de otra persona.
- El catálogo de vehículos y el registro de devoluciones son de escritura solo para operadores.
- El login tiene su propio límite de peticiones (10/min), separado del resto.

---

## Interfaz

SPA construida con `ui.sub_pages` de NiceGUI: la navegación no recarga la página y el estado
de sesión sobrevive entre secciones. Paleta de tres colores, según lo pedido:

| Color | Valor | Uso |
|-------|-------|-----|
| Azul | `#0D3B8C` | Encabezado, menú lateral, botones primarios |
| Azul claro | `#1565C0` | Acentos y distintivos de estado |
| Rojo | `#C62828` | Acciones destructivas, alertas y errores |
| Blanco | `#FFFFFF` | Fondo y tarjetas |

Secciones: Panel (indicadores), Usuarios, Vehículos, Reservas, Pagos y Devoluciones.

---

## Pruebas y verificación

```powershell
# Suite completa con cobertura
.\.venv\Scripts\python.exe -m pytest

# Todo lo que corre el CI, en el mismo orden
.\scripts\verificar.ps1
```

`verificar.ps1` reproduce en local los cuatro trabajos del pipeline: `ruff`, la suite con
umbral de cobertura, y `check --deploy --fail-level WARNING` contra el settings de
**producción**. Ese último es el que más se olvida, porque corre con una configuración
distinta a la de desarrollo y no lo cubre ningún test.

El pipeline añade un trabajo que verifica que el sistema **arranca**: migra, carga los datos
de demostración, levanta ambos procesos y comprueba que responden y que el login devuelve un
token. Un CI que solo pasa un linter da falsa seguridad.

---

## Estructura

```
SistemaArriendoVehiculos/
├── backend/
│   ├── config/settings/{base,dev,test,prod}.py   herencia real entre entornos
│   ├── core/                exceptions.py · api/{exception_handler,permissions,views}.py
│   └── apps/{usuarios,vehiculos,arriendos}/
├── frontend/
│   ├── main.py · api_client.py · theme.py · layout.py
│   ├── paginas/             login, panel, usuarios, vehiculos, reservas, pagos, devoluciones
│   └── static/css/app.css   sistema de diseño (tokens, elevación, componentes)
├── deploy/k8s/              manifiestos de Kubernetes (Kustomize)
├── infra/                   Terraform: namespace, config, secretos y volumen
├── docs/arquitectura.md     diseño y diagramas UML (Mermaid)
├── scripts/verificar.ps1
├── Dockerfile · docker-compose.yml · .dockerignore
├── Jenkinsfile              pipeline alternativo on-prem
├── requirements.txt · requirements-dev.txt · pyproject.toml
└── .env.example
```

---

## Tecnologías

| Componente | Versión |
|------------|---------|
| Python | 3.12+ (probado en 3.14.3) |
| Django | 6.1 |
| Django REST Framework | 3.18.0 |
| NiceGUI | 3.16.0 |
| Base de datos | SQLite |
| Servidor WSGI | gunicorn 23.0.0 (solo en contenedor) |
| Estáticos | WhiteNoise 6.8.2 (solo en `prod`) |
| Pruebas | pytest + pytest-django + pytest-cov |
| Estilo | ruff |
| Contenedores | Docker (multi-stage) + Compose |
| Orquestación | Kubernetes + Kustomize |
| Infraestructura | Terraform (~> 1.9) |
| CI/CD | GitHub Actions · Jenkins (alternativa on-prem) |

---

## Despliegue en contenedores

```bash
# Requiere SECRET_KEY y NICEGUI_STORAGE_SECRET en tu .env
docker compose up --build
```

Levanta tres servicios: `migraciones` (corre una vez y termina), `backend` y
`frontend`. A diferencia de `iniciar.bat`, esto comprueba que la **imagen de
producción** arranca de verdad —con `DEBUG=False`, gunicorn y estáticos
recolectados—, que es justo lo que el arranque de desarrollo no valida.

Las migraciones van en su propio contenedor y no en el arranque del backend:
con más de una réplica, varios procesos migrando a la vez sobre la misma base
chocan entre sí.

Para el clúster, ver [`deploy/k8s/`](deploy/k8s/) y la infraestructura previa en
[`infra/`](infra/). El diseño y los diagramas UML están en
[`docs/arquitectura.md`](docs/arquitectura.md).
