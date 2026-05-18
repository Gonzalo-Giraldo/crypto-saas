# Runtime Scheduler Ownership Design

## Objetivo

Definir semánticas de ownership, supervision y recovery del runtime scheduler
para ejecución desacoplada (AWS worker / external runtime execution)
manteniendo single runtime authority y fail-closed semantics.

## Principios

- Single runtime authority.
- Fail-closed ante ownership ambiguo.
- No split-brain runtime.
- Frontend observational only.
- Runtime authority backend-side.
- Advisory lock sigue siendo obligatorio.
- Ownership durable nunca reemplaza runtime lock DB-side.
- No automatic unsafe takeover.
- No broker mutation under ambiguous ownership.

## Problemas a resolver

- Worker/container restart.
- Zombie worker.
- Dead thread with stale ownership.
- Duplicate runtime workers.
- AWS multi-instance accidental execution.
- Lost heartbeat.
- Network partition.
- Runtime stale detection.
- Safe ownership recovery.

## Ownership concepts (draft)

### runtime_owner_id
Identificador lógico del owner runtime activo.

### runtime_instance_id
Identificador único de proceso/container/worker runtime.

### runtime_generation
Versión monotónica de ownership runtime.

### runtime_started_at
Timestamp de adquisición ownership.

### runtime_heartbeat_at
Último heartbeat válido del runtime owner.

## Core semantics (draft)

### Ownership acquisition
Un runtime worker sólo puede ejecutar runtime activo si:
- obtiene advisory lock
- ownership state es válido
- no existe owner activo saludable
- generation semantics son válidas

### Heartbeat
El owner runtime debe actualizar heartbeat periódicamente.

### Stale runtime
Un runtime owner puede considerarse stale si heartbeat excede threshold definido.

### Recovery
Recovery sólo permitido bajo reglas explícitas y auditables.

### Split-brain prevention
Nunca permitir múltiples runtime owners activos simultáneamente.

### Fail-closed
Ante estado ambiguo:
- no mutation
- no runtime takeover
- no broker authority escalation

## Relationship with scheduler_runtime_loop.py

`scheduler_runtime_loop.py` sigue siendo runtime authority shell.

Ownership semantics futuras deben integrarse sin romper:
- lifecycle semantics
- status projection
- effective state semantics
- advisory lock governance
- operational observability

## Relationship with runtime_status.py

Frontend consume projection operacional.
Frontend nunca decide ownership runtime.

## Relationship with AWS deployment

AWS workers deben respetar:
- ownership semantics
- advisory lock semantics
- stale recovery semantics
- single runtime authority

## Relationship with runtime DB

Ownership durable pertenece a runtime DB.
Nunca a DATA DB.

## Pending design decisions

- heartbeat interval
- stale timeout threshold
- generation increment semantics
- takeover rules
- recovery authorization semantics
- manual override semantics
- pause/resume semantics
- worker identity format
- graceful shutdown semantics
- reconciliation with advisory lock loss


## Ownership lifecycle draft

### INIT
Worker creado pero todavía sin authority runtime.

### ACQUIRING
Worker intentando adquirir advisory lock y ownership válido.

### ACTIVE
Worker con advisory lock válido y ownership runtime activo.

Permitido:
- scheduler execution
- heartbeat updates
- runtime observability updates

### STALE
Ownership heartbeat excedió stale threshold.

No permitido:
- broker mutation
- runtime takeover automático ambiguo

Requiere:
- explicit recovery semantics

### RECOVERING
Proceso controlado de recuperación ownership.

Debe:
- revalidar advisory lock
- validar stale ownership
- validar generation semantics

### STOPPING
Shutdown solicitado.

Permitido:
- graceful shutdown
- heartbeat final
- observability finalization

No permitido:
- new runtime acquisition

### STOPPED
Worker detenido sin authority runtime.

### LOST_LOCK
Worker perdió advisory lock inesperadamente.

Debe:
- fail-closed inmediatamente
- detener runtime mutation
- detener scheduler execution
- marcar operator attention required

### FAILED
Worker encontró estado inconsistente o excepción fatal runtime-side.

Debe:
- fail-closed
- detener runtime authority
- requerir recovery explícito

### ZOMBIE_SUSPECTED
Ownership ambiguo detectado.

Ejemplos:
- heartbeat inconsistente
- duplicate owner detection
- advisory lock inconsistency
- stale runtime conflict

Debe:
- bloquear runtime mutation
- requerir intervención/recovery explícito

## Ownership transition principles

### Illegal transitions
No permitir:
- ACTIVE -> ACTIVE con owner distinto simultáneo
- STALE -> ACTIVE sin recovery válido
- LOST_LOCK -> ACTIVE sin reacquisition explícita
- FAILED -> ACTIVE sin recovery explícito

### Fail-closed transitions
Ante transición ambigua:
- detener mutation authority
- detener runtime execution
- elevar operator attention required

### Advisory lock supremacy
Ownership durable nunca reemplaza advisory lock.

Advisory lock sigue siendo autoridad runtime inmediata.

### Runtime DB supremacy
Runtime DB sigue siendo source of truth para ownership runtime.

DATA DB nunca define runtime authority.


## Ownership reconciliation semantics (draft)

### DB ACTIVE but advisory lock missing

Estado inválido.

Debe:
- transition -> LOST_LOCK
- fail-closed inmediatamente
- detener runtime execution
- bloquear mutation authority
- marcar operator attention required

No permitido:
- continuar runtime execution sólo por ownership DB-side

### Advisory lock active but heartbeat stale

Estado ambiguo.

Debe:
- bloquear runtime takeover automático
- requerir reconciliation explícita
- validar si runtime owner sigue saludable

No permitido:
- takeover inmediato sólo por stale heartbeat

### Thread dead but DB ACTIVE

Debe:
- transition -> STALE o FAILED según contexto
- marcar operator attention required
- bloquear mutation authority

### AWS/container abrupt restart

Nuevo worker debe:
- reacquire advisory lock
- validar ownership semantics
- validar stale ownership
- validar generation semantics

No permitido:
- asumir ownership automáticamente por restart

### Network partition

Ante estado inconsistente:
- fail-closed
- bloquear mutation authority
- evitar split-brain
- requerir reconciliation explícita

### Duplicate stale detection

Si múltiples workers consideran stale simultáneamente:
- advisory lock sigue siendo autoridad inmediata
- sólo un worker puede continuar acquisition
- ownership durable no puede override advisory lock

### Ownership reconciliation priority

Orden de autoridad:

1. Advisory lock válido
2. Runtime process health
3. Ownership generation semantics
4. Heartbeat freshness
5. Lifecycle state projection

### Runtime mutation safety

Nunca permitir:
- broker mutation
- runtime mutation
- ownership takeover

si:
- ownership ambiguity existe
- reconciliation incompleta
- advisory lock inconsistente
- runtime health desconocida

### Recovery auditability

Todo recovery debe ser:
- observable
- auditado
- traceable
- explainable post-mortem


## Non-goals and prohibited behaviors

### Frontend authority prohibition

Frontend must never:
- decide runtime ownership
- force runtime takeover
- override advisory lock semantics
- bypass runtime reconciliation
- trigger broker mutation directly

Frontend is observational and operational-request only.

### Automatic unsafe recovery prohibition

System must never:
- auto-takeover ambiguous ownership
- auto-recover inconsistent runtime state
- continue execution under reconciliation ambiguity
- ignore advisory lock inconsistency
- assume stale owner is dead without validation

### Broker mutation prohibition under ambiguity

Broker/runtime mutation is prohibited when:
- ownership ambiguity exists
- runtime health is unknown
- advisory lock state is inconsistent
- reconciliation is incomplete
- duplicate ownership is suspected
- stale recovery is unresolved

### DATA DB authority prohibition

DATA DB must never:
- define runtime ownership
- define runtime authority
- authorize scheduler execution
- authorize broker mutation
- replace runtime DB authority

### Runtime ownership override prohibition

No runtime component may:
- bypass advisory lock semantics
- override generation validation
- suppress stale detection
- suppress operator attention escalation
- continue ACTIVE execution after LOST_LOCK detection

### Split-brain tolerance prohibition

System must never tolerate:
- simultaneous ACTIVE owners
- concurrent runtime mutation authority
- duplicated scheduler execution authority
- ambiguous ownership continuation

Fail-closed behavior is mandatory.

