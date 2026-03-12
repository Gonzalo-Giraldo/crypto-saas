# Scheduler and Concurrency Model

## 1. Purpose of This Document

This document explains how scheduling, concurrency, and execution coordination work in the trading platform.

The goal is to make explicit:

- how the scheduler operates
- how tenant loops are executed
- how concurrency is controlled
- where duplicate execution risks may exist
- which mechanisms mitigate those risks

This document reflects the **current architecture**, not a proposed redesign.

---

# 2. Scheduler Architecture

The platform runs an **internal scheduler embedded inside the API process**.

Scheduler code lives primarily in:


apps/api/app/main.py


Key functions:


lifespan()
_start_auto_pick_scheduler()
_stop_auto_pick_scheduler()
_scheduler_loop()
_auto_pick_tick_once_with_lock()
_auto_pick_tick_once()


The scheduler runs in a **background daemon thread** started during application startup.

---

# 3. Scheduler Startup

During FastAPI application startup:


lifespan()


If configuration allows it:


AUTO_PICK_INTERNAL_SCHEDULER_ENABLED = true


the system launches a daemon thread:


auto-pick-scheduler


which runs continuously during the life of the application process.

---

# 4. Scheduler Loop

The main loop:


_scheduler_loop()


performs the following steps repeatedly:

1. Sleep for a configured interval


AUTO_PICK_INTERVAL_MINUTES


2. Execute a scheduler tick:


_auto_pick_tick_once_with_lock()


3. Log execution statistics.

---

# 5. Global Scheduler Lock

To prevent multiple instances of the scheduler running simultaneously across replicas, the system uses a **PostgreSQL advisory lock**.

Implementation:


SELECT pg_try_advisory_lock(:lock_key)


Lock key:


_AUTO_PICK_LOCK_KEY = 887731


Execution flow:


if pg_try_advisory_lock succeeds:
run scheduler tick
release lock
else:
skip this cycle


This ensures only **one scheduler instance executes globally**.

---

# 6. Behavior in SQLite Environments

When the system runs on SQLite:


DATABASE_URL.startswith("sqlite")


the advisory lock mechanism is **disabled**.

In this configuration:

- multiple scheduler loops may run concurrently
- no protection exists against overlapping cycles

SQLite environments should therefore be treated as **development-only**.

---

# 7. Scheduler Workflows

Each scheduler tick executes multiple operational flows.

Primary flows:


run_exit_tick_for_tenant()
run_market_monitor_tick_for_tenant()
run_auto_pick_tick_for_tenant()
run_learning_pipeline_tick()


These flows are executed **per tenant**.

The scheduler enumerates tenants and executes each flow sequentially.

---

# 8. Manual Execution Paths

Some scheduler actions can also be triggered manually via API endpoints.

Example:


POST /admin/auto-pick/tick


This endpoint triggers the same internal logic used by the scheduler.

Therefore manual execution may occur concurrently with scheduler execution.

---

# 9. Concurrency Control Mechanisms

The platform uses several mechanisms to limit concurrency risks.

### 9.1 Advisory Lock

Used to prevent multiple scheduler instances running simultaneously.

Location:


main.py
_auto_pick_tick_once_with_lock()


Applies only when PostgreSQL is used.

---

### 9.2 State Machines

Signal and position state transitions are guarded by explicit transition checks.

Examples:


assert_signal_transition()
assert_position_transition()


These checks ensure valid lifecycle transitions such as:


CREATED → EXECUTING → OPENED


---

### 9.3 Idempotent Requests

Several endpoints implement idempotent request protection.

Mechanism:


X-Idempotency-Key
consume_idempotent_response()
store_idempotent_response()


Idempotency is mandatory when:


dry_run = false

Hardening reciente:

- `open_from_signal` ahora usa un bloqueo transaccional de la fila `Signal` y comprueba la existencia de posiciones abiertas con el mismo `signal_id` antes de crear una nueva posición.
- el flujo auto-pick valida la exposición final con la cantidad normalizada del broker (`execution_preview`), evitando discrepancia entre el cálculo preliminar y la ejecución final.
- en auto-pick live (`dry_run=false`), se añadió una barrera semántica de intención mediante `pg_try_advisory_lock` sobre una conexión dedicada (`engine.connect()`), indexada por (tenant, usuario, exchange, símbolo, lado). El lock se adquiere antes de `reserve_idempotent_intent` y se libera en `finally` sobre la misma conexión, garantizando affinidad de conexión tras los commits del pool de SQLAlchemy. En no-Postgres: fail-closed sin equivalente real.


---

### 9.4 Trading Kill Switch

Trading execution is gated by:


assert_trading_enabled()


The kill switch is tenant-scoped:


trading_enabled:{tenant_id}


---

# 10. Potential Concurrency Scenarios

Despite the protections above, several concurrency situations remain possible.

---

## 10.1 Scheduler vs Scheduler

If PostgreSQL advisory locking works correctly:

- overlapping scheduler loops cannot run simultaneously.

If SQLite is used:

- multiple loops may execute concurrently.

Risk level:


High (SQLite)
Low (Postgres)


---

## 10.2 Scheduler vs Manual API

Manual API endpoints may execute the same flows triggered by the scheduler.

Examples:


auto-pick
pretrade scans
signal operations
position opening


This means a manual action can occur simultaneously with a scheduler tick.

---

## 10.3 Signal Claim Concurrency

Signals are claimed through:


POST /signals/claim


Signals with status:


CREATED


are moved to:


EXECUTING


If two requests attempt to claim signals simultaneously:

- both may read the same signal rows
- transition checks may reject one
- race windows may still exist without row-level locks.

---

## 10.4 Position Creation Concurrency

Positions are opened through:


POST /positions/open_from_signal


The endpoint requires signal status:


EXECUTING


However, if two requests operate on the same signal concurrently:

- both may pass validation
- both may create positions

unless additional locking exists.

---

## 10.5 Auto-Pick Concurrency

Auto-pick logic occurs inside:


run_auto_pick_tick_for_tenant()


and may also be invoked through API calls.

Multiple threads could therefore evaluate the same candidates simultaneously.

Partial mitigation (commit 31176d6): the live path (`dry_run=false`) acquires a semantic advisory lock keyed by (tenant, user, exchange, symbol, side) before idempotent reservation and dispatch. Two concurrent live auto-pick calls with equivalent material intent cannot both proceed to dispatch. Dry-run and non-Postgres paths are not covered by this mechanism.

Additional bounded mitigation (commit a32fb7a): Binance live auto-pick SPOT BUY eligible in USDT now runs a broker-side pre-dispatch guard (`can_trade` and `USDT free` vs `estimated_notional * 1.02`) with fail-closed behavior when broker state is not usable.

---

## 10.6 Exposure Calculation Race

Exposure checks rely on current database state.

Location:


trading_controls.assert_exposure_limits()


Exposure is calculated using currently open positions.

If two executions occur simultaneously:

- both may see the same exposure
- both may proceed
- combined exposure may exceed limits.

---

## 10.7 Broker Execution Retries

Broker execution is performed in:


execution_runtime.py


Example:


execute_binance_test_order_for_user()


Orders use:


deterministic `client_order_id` only in hardened Binance live auto-pick when `intent_key` exists; legacy behavior outside that flow remains non-deterministic


If retries occur:

- outside the hardened Binance live auto-pick flow, a second request may generate a different order ID
- the broker may still treat it as a new order when `intent_key` is unavailable or the flow remains legacy.

---

# 11. Idempotency Coverage

Idempotency is enforced in several critical paths.

Mandatory when:


dry_run = false


However:

- dry-run paths may execute without idempotency keys
- internal scheduler flows do not rely on external idempotency.

---

# 12. Remaining Risk Areas

The following concurrency risks remain possible:

1. concurrent `open_from_signal` calls
2. broker retries producing new orders outside hardened Binance live auto-pick or when `intent_key` is unavailable
3. scheduler competing with manual operations (partially mitigated for live `dry_run=false` auto-pick under PostgreSQL; residual for dry-run and non-Postgres paths)
4. broker-state gating remains partial; new pre-dispatch guard is limited to Binance live SPOT BUY eligible in USDT and is not general reconciliation
5. exposure limits calculated from stale state
6. SQLite environments running overlapping schedulers
7. idempotency not enforced in dry-run flows
8. candidate evaluation performed concurrently

---

# 13. Operational Safety Summary

The system currently relies on multiple safety layers:

- scheduler advisory lock
- signal state machine
- idempotency keys
- kill switch
- exposure controls
- audit logging

These layers significantly reduce risk but do not eliminate all concurrency scenarios.

---

# 14. Design Philosophy

The system follows a **defensive execution model**:

1. validate signal
2. evaluate risk
3. check exposure
4. enforce idempotency
5. apply execution guards
6. dispatch order
7. audit outcome

This layered approach is designed to reduce the probability of duplicate or unsafe trading actions.

---

# 15. Future Hardening Areas (Documentation Only)

Possible areas for further strengthening include:

- deterministic broker order identifiers
- stricter idempotency requirements
- row-level locking for signal processing
- exposure checks aligned with final execution quantity
- concurrency testing scenarios

These items are outside the scope of the current document and belong to future hardening work.

---

# 16. Final Note

Scheduler behavior and concurrency management are critical aspects of trading system safety.

Any change affecting:

- scheduler logic
- signal lifecycle
- position creation
- broker execution
- exposure validation

must be reviewed carefully to avoid introducing duplicate trading or inconsistent system state.

