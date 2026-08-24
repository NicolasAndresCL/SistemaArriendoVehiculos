# Arquitectura y diseño — Sistema de Arriendo de Vehículos

Documento de diseño de la asignatura **Diseño de Software (IEI-050)**.
Los diagramas se escriben en Mermaid y no como imágenes exportadas: así viven
en el repositorio, entran en el *diff* de cada cambio y no se desincronizan en
silencio del código que describen.

---

## 1. Decisiones de proceso

| Decisión | Categoría | Justificación |
|---|---|---|
| **Iterativo-incremental** | Modelo de ciclo de vida | Los requisitos del enunciado se refinaron al ver el sistema funcionando. Cascada habría fijado el diseño antes de tener esa información. |
| **Scrum** | Marco de gestión | Implementa el modelo iterativo-incremental mediante sprints. No es un ciclo de vida en sí. |
| **Prototipado de interfaz** | Técnica de requisitos | Validar las pantallas antes de comprometer reglas de negocio. |

> La distinción importa: *modelo* es la estructura de alto nivel, *marco* es
> cómo se ejecuta ese modelo, *técnica* es una herramienta puntual dentro del
> proceso. Confundirlos es un error de categoría.

---

## 2. Vista de componentes

Dos procesos separados. La interfaz **nunca** toca el ORM: consume la API igual
que cualquier otro cliente. Eso mantiene las reglas de negocio en un solo lugar
y permite probarlas sin levantar un servidor.

```mermaid
flowchart LR
    Navegador["Navegador"]
    Front["NiceGUI :8080<br/>frontend/<br/><i>solo presentación</i>"]
    Api["Django + DRF :8000<br/>backend/<br/><i>reglas de negocio</i>"]
    Db[("SQLite<br/>db.sqlite3")]

    Navegador -->|HTTPS + WebSocket| Front
    Front -->|"HTTP + Token<br/>JSON /api/v1/..."| Api
    Api -->|ORM| Db
```

### Capas del backend

```mermaid
flowchart TB
    V["views.py<br/><i>traduce HTTP</i>"]
    S["serializers.py<br/><i>valida y presenta</i>"]
    Sv["services.py<br/><i>reglas de negocio</i>"]
    M["models.py<br/><i>estructura y estado</i>"]
    E["core/exceptions.py<br/><i>errores de dominio</i>"]

    V --> S
    V --> Sv
    Sv --> M
    Sv -.lanza.-> E
    E -.->|"un único manejador<br/>traduce a HTTP"| V
```

Las vistas no arman respuestas de error a mano: los servicios **lanzan**
excepciones de dominio y un único manejador las traduce al contrato
`{"error": {"codigo", "mensaje", "detalle"}}`. El `codigo` es el identificador
estable que consume la interfaz; el `mensaje` en español puede cambiar sin
romper a nadie.

---

## 3. Diagrama de clases del dominio

```mermaid
classDiagram
    class Usuario {
        -email: str
        -rut: str
        -nombre: str
        -apellido: str
        -rol: Rol
        -licencia_numero: str
        -licencia_vencimiento: date
        +licencia_vigente_al(fecha: date) bool
        +nombre_completo() str
    }

    class Vehiculo {
        -patente: str
        -marca: str
        -modelo: str
        -anio: int
        -categoria: Categoria
        -tarifa_diaria: Decimal
        -kilometraje: int
        -estado: Estado
        +esta_disponible() bool
    }

    class Reserva {
        -fecha_inicio: date
        -fecha_fin: date
        -estado: Estado
        -monto_estimado: Decimal
        +dias() int
        +esta_pagada() bool
    }

    class Pago {
        -monto: Decimal
        -medio: Medio
        -estado: Estado
        -comprobante: str
        -fecha_pago: datetime
    }

    class Devolucion {
        -fecha_devolucion: date
        -kilometraje_final: int
        -nivel_combustible: NivelCombustible
        -cargo_adicional: Decimal
        -dias_atraso: int
    }

    Usuario "1" --> "0..*" Reserva : realiza
    Vehiculo "1" --> "0..*" Reserva : es arrendado en
    Reserva "1" *-- "0..*" Pago : registra
    Reserva "1" *-- "0..1" Devolucion : cierra con
```

**Lectura de las multiplicidades** (se leen cruzadas): *un* usuario realiza
*cero o muchas* reservas; *cada* reserva pertenece a *exactamente un* usuario.

**Por qué composición (◆) entre `Reserva` y sus partes:** un pago o una
devolución **no significan nada sin su reserva** — si la reserva desaparece,
la parte deja de tener sentido. Por eso `Pago` y `Devolucion` se borran en
cascada con ella. En cambio, `Usuario` y `Vehiculo` existen por su cuenta: su
relación con `Reserva` es una asociación simple, no una composición.

**Navegabilidad:** la flecha va de `Usuario`/`Vehiculo` hacia `Reserva` porque
es la reserva la que guarda las claves foráneas. Coincide con el código: en
Django, `Reserva.usuario` es el atributo real y `usuario.reservas` es el acceso
inverso que genera el ORM.

> Las cinco entidades se agrupan en **tres apps** (`usuarios`, `vehiculos`,
> `arriendos`) según su límite de agregado, no una app por modelo: `Reserva`,
> `Pago` y `Devolucion` forman un solo agregado con la reserva como raíz.

---

## 4. Máquina de estados de la reserva

Las transiciones no permitidas lanzan `TransicionNoPermitidaError`; no se
"corrigen" en silencio.

```mermaid
stateDiagram-v2
    [*] --> PENDIENTE : crear_reserva()
    PENDIENTE --> CONFIRMADA : registrar_pago()
    PENDIENTE --> CANCELADA : cancelar()
    CONFIRMADA --> EN_CURSO : registrar_retiro()
    CONFIRMADA --> CANCELADA : cancelar()
    EN_CURSO --> FINALIZADA : registrar_devolucion()
    CANCELADA --> [*]
    FINALIZADA --> [*]
```

Estado del vehículo asociado: pasa a `ARRENDADO` en `registrar_retiro()` y
vuelve a `DISPONIBLE` (o a `MANTENIMIENTO`, si hubo daños) al registrar la
devolución.

---

## 5. Diagrama de secuencia — registrar un pago

Escenario con su camino de error explícito, en un fragmento `alt`, no como un
comentario al margen.

```mermaid
sequenceDiagram
    actor Operador
    participant UI as NiceGUI
    participant API as views.py
    participant SRV as services.py
    participant BD as ORM

    Operador->>UI: Confirma el pago
    activate UI
    UI->>API: POST /api/v1/reservas/{id}/pagar/
    activate API
    API->>SRV: registrar_pago(reserva, monto, medio)
    activate SRV
    SRV->>BD: SELECT reserva FOR UPDATE
    BD-->>SRV: reserva

    alt La reserva admite pago
        SRV->>BD: INSERT Pago
        SRV->>BD: UPDATE Reserva.estado = CONFIRMADA
        SRV-->>API: Pago
        API-->>UI: 201 Created
        UI-->>Operador: "Pago registrado"
    else Ya estaba pagada o el estado no lo permite
        SRV--xAPI: PagoDuplicadoError
        Note over API: El manejador único traduce<br/>la excepción de dominio a HTTP
        API-->>UI: 409 {"error": {"codigo": "pago_duplicado"}}
        UI-->>Operador: Notificación en rojo
    end
    deactivate SRV
    deactivate API
    deactivate UI
```

---

## 6. Casos de uso

```mermaid
flowchart TB
    subgraph Sistema["Sistema de Arriendo de Vehículos"]
        CU1(["Registrar reserva"])
        CU2(["Registrar pago"])
        CU3(["Registrar retiro"])
        CU4(["Registrar devolución"])
        CU5(["Gestionar catálogo"])
        CU6(["Validar sesión"])
        CU7(["Aplicar cargo por atraso"])
    end

    Operador["Operador"]
    Cliente["Cliente"]

    Operador --- CU1
    Operador --- CU2
    Operador --- CU3
    Operador --- CU4
    Operador --- CU5
    Cliente --- CU1

    CU1 -.->|"«include»"| CU6
    CU2 -.->|"«include»"| CU6
    CU7 -.->|"«extend»"| CU4
```

**`«include»` vs `«extend»`** — se confunden casi siempre:

- **`«include»`**: el caso base **siempre** ejecuta el incluido. "Registrar
  reserva" siempre valida la sesión. La flecha va del **base al incluido**.
- **`«extend»`**: comportamiento **condicional**. "Aplicar cargo por atraso"
  solo ocurre si la devolución llega tarde. La flecha va del **extensión al
  base**, en sentido contrario.

Los actores son **roles**, no personas ni cargos, y quedan fuera del límite del
sistema.

---

## 7. Vista de despliegue

```mermaid
flowchart TB
    subgraph Cluster["Clúster Kubernetes · namespace arriendos"]
        Ing["Ingress<br/>nginx + TLS"]
        subgraph F["Deployment frontend (2 réplicas)"]
            FP["Pod NiceGUI :8080"]
        end
        subgraph B["Deployment backend (2 réplicas)"]
            BP["Pod gunicorn :8000"]
        end
        Job["Job migraciones<br/><i>corre una vez, antes del rollout</i>"]
        PVC[("PVC arriendos-datos")]
    end

    Internet(["Internet"]) --> Ing
    Ing --> FP
    FP -->|"NetworkPolicy<br/>permite solo esto"| BP
    BP --> PVC
    Job --> PVC
```

Decisiones y su motivo:

- **Solo la interfaz se expone.** La API queda en `ClusterIP` porque su único
  cliente es el frontend; publicarla ampliaría la superficie sin necesidad.
- **Migraciones en un `Job` aparte.** Con dos réplicas, ponerlas en el arranque
  del contenedor haría que ambos procesos migraran a la vez sobre la misma base.
- **Sesión pegajosa en el Ingress.** NiceGUI mantiene un WebSocket con estado
  en el pod: sin afinidad, la reconexión puede caer en otro pod y perder la sesión.

Detalle de los manifiestos en [`deploy/k8s/`](../deploy/k8s/) y de la
infraestructura previa en [`infra/`](../infra/).

---

## 8. Correspondencia diseño ↔ código

Un diagrama que no coincide con el código es documentación falsa. Esta tabla es
lo que hay que revisar al modificar el modelo:

| En UML | En el código |
|---|---|
| `Usuario "1" --> "0..*" Reserva` | `Reserva.usuario = ForeignKey(..., related_name="reservas")` |
| `Reserva "1" *-- "0..*" Pago` (composición) | `Pago.reserva = ForeignKey(Reserva, on_delete=CASCADE)` |
| `Reserva "1" *-- "0..1" Devolucion` | `Devolucion.reserva = OneToOneField(Reserva, on_delete=CASCADE)` |
| Multiplicidad `0..1` | `OneToOneField` — una reserva se devuelve una sola vez |
| Transición no permitida | `TransicionNoPermitidaError` en `services.py` |

**Al cambiar el modelo, auditar este documento en el mismo commit.** Un
diagrama obsoleto es peor que uno ausente: alguien lo va a creer.
