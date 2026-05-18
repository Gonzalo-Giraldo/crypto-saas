# Runtime Scheduler Architecture

## Objetivo
Descripción del sistema, sus módulos y flujo de datos.

## Módulos
- Context Builder
- Observability
- Runtime Flow
- Runtime State
- Runtime Adapter
- Runtime Dependencies

## Flujo
1. Scheduler tick inicia
2. Carga estado runtime
3. Ejecuta flujos legacy y auto-pick
4. Captura observaciones y shadow tick
5. Genera tick details
6. Construye runtime flow result
7. Persiste observabilidad y estado runtime
8. Maneja errores y excepciones
...

## P2 scheduler authority audit

The runtime scheduler authority remains `apps/api/app/services/scheduler_runtime_loop.py`.

P2 must not introduce a second scheduler runner or duplicate lifecycle ownership.
Future extraction must preserve:

- advisory lock governance
- overlap blocked journal semantics
- scheduler lifecycle desired/effective state
- thread alive projection
- backend runtime authority
- frontend observational-only projection

`apps/api/app/services/runtime_scheduler/worker_control.py` and
`apps/api/app/services/runtime_scheduler/scheduler_worker.py` are reusable scaffolding only.
They are not active runtime authority until the existing scheduler semantics are migrated safely.

