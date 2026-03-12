# CHANGE COMMUNICATION LOG

## Hardening de advisory lock semántico en auto-pick live usando conexión dedicada

- Commit: 31176d6 hardening: add dedicated advisory lock connection for live auto-pick intent
- Se reemplazó el uso de `db.execute()` para `pg_try_advisory_lock`/`pg_advisory_unlock` en `_auto_pick_from_scan` por una conexión dedicada explícita (`engine.connect()`), evitando el problema de pool affinity de SQLAlchemy tras `db.commit()` en `reserve_idempotent_intent`.
- Ahora, en el flujo live (`dry_run=false`), la barrera semántica (tenant, usuario, exchange, símbolo, lado) es fiable a través de los commits del ORM Session: acquire y unlock ocurren siempre sobre la misma conexión física.
- El unlock y el cierre de la conexión dedicada ocurren en `finally`, best-effort, sin enmascarar el error principal del flujo.
- Mitigación parcial: aplica solo al flujo live bajo Postgres. En no-Postgres, el comportamiento es conservador/fail-closed (`semantic_intent_lock_requires_postgres`), no equivalente.
- No resuelve race conditions fuera del tramo auto-pick live ni en rutas dry_run.
- Alcance: `apps/api/app/api/ops.py` únicamente. No modifica: `idempotency.py`, `main.py`, `signals.py`, `positions.py`, `trading_controls.py`, `risk_engine.py`.

---

## Hardening de idempotencia pre-dispatch en auto-pick live

- Commit: 0b0e21a hardening: add pre-dispatch idempotency reservation for live auto-pick
- Se implementó una reserva idempotente pre-dispatch en auto-pick live usando la tabla IdempotencyKey.
- Ahora, antes de despachar al broker, se reserva la intención idempotente y se bloquea la ejecución concurrente equivalente.
- La intención se finaliza tanto en éxito como en errores controlados del dispatch, evitando dejar filas in_progress salvo en crash abrupto.
- Mitigación parcial: filas in_progress pueden quedar stale si el proceso se interrumpe inesperadamente.
- No resuelve duplicados a nivel broker si el identificador externo no es determinista.
- Documentación y código alineados; mitigación activa pero no total.

---

## Hardening de execution validation y duplicate prevention en open_from_signal

- Estado:
  - aprobado
  - commits realizados
  - documentación actualizada: sí
  - listo para merge: sí

- Objetivo:
  Reducir dos riesgos operativos relevantes del sistema:
  1. desalineación entre qty validada por exposición y qty final broker-normalized en auto-pick
  2. doble apertura concurrente de posiciones desde la misma señal en open_from_signal

- Riesgo que mitigó:
  - exposición evaluada con qty preliminar en vez de qty final canónica
  - apertura duplicada por carrera concurrente sobre el mismo signal_id
  - trazabilidad insuficiente de requested/sized/normalized qty en auto-pick

- Alcance:
  - archivos tocados:
    - apps/api/app/api/ops.py
    - apps/worker/app/engine/execution_runtime.py
    - apps/api/app/api/positions.py
    - docs/TRADING_RISK_GUARDS.md
    - docs/PRODUCTION_READINESS.md
    - docs/SCHEDULER_AND_CONCURRENCY_MODEL.md
  - superficies NO tocadas:
    - apps/api/app/api/signals.py
    - apps/api/app/main.py
    - apps/api/app/services/risk_engine.py
    - apps/api/app/services/trading_controls.py
    - scheduler redesign
    - reconciliación broker
    - modularización formal del kernel

- Resumen técnico:
  1. Se añadió `resolve_execution_quantity_preview(...)` en execution_runtime.py.
  2. Auto-pick ahora resuelve una qty canónica broker-aware antes del dispatch.
  3. `assert_exposure_limits(...)` en auto-pick usa `normalized_qty` y `price_estimate` del preview canónico.
  4. `selected_qty` quedó alineada con la qty final canónica.
  5. Se añadieron campos de trazabilidad:
     - `selected_qty_requested`
     - `selected_qty_sized`
     - `selected_qty_normalized`
     - `selected_price_estimate`
     - `selected_estimated_notional`
     - `selected_qty_normalization_source`
  6. En `open_from_signal`, la `Signal` se carga con lock transaccional (`with_for_update()`).
  7. Antes de crear posición, se verifica si ya existe una `Position` `OPEN` con el mismo `signal_id`; si existe, se responde `409`.

- Invariantes preservadas:
  - fail-closed
  - idempotencia actual en rutas live
  - paper/live separation
  - auditabilidad
  - tenant isolation
  - sin refactor amplio
  - sin expansión lateral del cambio

- Impacto operativo:
  - auto-pick valida exposición con qty final más cercana a la ejecución real
  - disminuye el riesgo de mismatch entre sizing/exposure/normalización broker
  - `open_from_signal` reduce el riesgo principal de doble apertura concurrente
  - no cambia scheduler
  - no cambia signals.py
  - no resuelve aún por completo duplicados scheduler/manual ni broker idempotency total

- Validación:
  - revisión arquitectónica de diff real en:
    - ops.py
    - execution_runtime.py
    - positions.py
  - verificación semántica de estados:
    - Position: `OPEN` / `CLOSED`
    - Signal: `CREATED`, `EXECUTING`, `OPENED`, `COMPLETED`
  - validación de que `Position.status == "OPEN"` es condición correcta para bloquear duplicados por `signal_id`

- Documentación actualizada:
  - docs/TRADING_RISK_GUARDS.md
  - docs/PRODUCTION_READINESS.md
  - docs/SCHEDULER_AND_CONCURRENCY_MODEL.md

- Commit(s):
  - 0a1be5f hardening: align auto-pick exposure with broker-normalized qty via execution_preview
  - ccae181 hardening: lock signal and prevent duplicate open_from_signal by existing open position

- Sigue abierto:
  - broker order idempotency determinística
  - scheduler vs manual race conditions fuera de open_from_signal
  - duplicate prevention en auto-pick más allá del exposure hardening
  - reconciliación broker centralizada
  - locking más fino en otras superficies

- Siguiente prioridad recomendada:
  Duplicate prevention / execution intent protection en auto-pick o frontera scheduler/manual, con alcance mínimo y sin rediseño grande.
