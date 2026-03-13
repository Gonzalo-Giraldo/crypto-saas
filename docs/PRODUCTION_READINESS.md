# Production Readiness Assessment

## 1. Purpose

This document evaluates whether the trading platform is ready for **real trading environments**.

The objective is to assess:

- architectural safety
- trading execution reliability
- duplication protection
- risk controls
- broker integration safety
- operational observability

This document does not describe how the system works.  
Instead it evaluates **whether the system can safely operate in production trading environments**.

---

# 2. System Overview

The platform is a **multi-tenant automated trading system** supporting:

- multiple users
- multiple broker-connected accounts
- automated signal execution
- manual signal execution
- background scheduler operations
- paper trading and guarded live trading

Supported brokers:

- BINANCE
- IBKR

The system includes:

- internal scheduler
- pretrade validation pipeline
- risk control layers
- exposure limits
- execution guards
- audit logging

---

# 3. Architecture Readiness

### Status: **GOOD**

Strengths:

- layered trading pipeline
- strong separation between API, services, and execution runtime
- multi-tenant design
- explicit trading guardrails
- documented architecture

Key modules are clearly separated:


API layer
Services layer
Trading engine
Execution runtime
Broker adapters
Scheduler


Risks:

- hybrid tenant isolation (tenant_id + user_id) increases complexity
- scheduler embedded in API process may complicate scaling.

---

# 4. Trading Engine Readiness

### Status: **MODERATE**

Strengths:

- explicit pipeline stages
- pretrade evaluation layer
- candidate scoring
- liquidity gating
- execution guardrails

Weaknesses:

- sizing model is heuristic rather than capital-based
- candidate qty origin varies (input vs universe)
- SELL adjustment is hardcoded (0.35 multiplier)
- exposure validation uses pre-adjusted qty.

Impact:

- safe enough for conservative operation
- but sizing logic could produce inconsistent behavior.

---

# 5. Scheduler Safety

### Status: **GOOD WITH CONDITIONS**

Strengths:

- advisory lock protects scheduler in PostgreSQL
- tick-based execution
- per-tenant processing model
- clear operational logs

Risks:

- SQLite environments have no scheduler locking
- scheduler shares process with API
- manual endpoints can trigger same flows concurrently (partial mitigation for live auto-pick path under PostgreSQL via semantic intent advisory lock, commit 31176d6).

Operational requirement:

Production must use **PostgreSQL advisory locks**.

SQLite environments are not production-safe.

---

# 6. Duplicate Execution Protection

### Status: **MODERATE**

Existing protections:

- idempotency keys for live execution
- signal lifecycle state transitions
- advisory lock for scheduler
- semantic intent advisory lock in live auto-pick path (PostgreSQL only, commit 31176d6)
- deterministic Binance `client_order_id` in hardened live auto-pick when `intent_key` exists (commit 5964cac)
- broker-side pre-dispatch USDT spot guard for Binance live auto-pick SPOT BUY (commit a32fb7a)
- fail-closed guard in Binance dispatcher when `_send_binance_test_order` is invoked without `client_order_id` (commit 034c41e)
- fail-closed guard in IBKR dispatcher path when `send_ibkr_test_order` is invoked without explicit `order_ref` (commit c531ef2)
- fail-closed guard in Binance quantity preparation when `min_notional > 0` but no usable price is available (commit b16cade)
- fail-closed guard in Binance quantity preparation when symbol metadata indicates non-trading status or MARKET order type not allowed (commit e3e418f)
- audit logging

Remaining risks:

- `open_from_signal` concurrency puede abrir posiciones duplicadas si las filas de señal no se bloquean; se agregó hardening con `SELECT ... FOR UPDATE` y check `Position.signal_id + status == OPEN` para mitigar este vector, pero sigue siendo un mecanismo de protección aditivo.
- Binance auto-pick live endurecido ya no usa `client_order_id` aleatorio cuando existe `intent_key`, pero fuera de ese flujo se mantiene comportamiento legacy
- el guard fail-closed del dispatcher Binance protege contra invocaciones directas sin `client_order_id`, pero depende del contrato del pipeline legítimo y no reemplaza idempotency, advisory lock ni broker-side guards
- el guard fail-closed del path IBKR protege contra invocaciones directas sin `order_ref`, pero depende del contrato del pipeline legítimo y no reemplaza idempotency, advisory lock, broker-side guards ni reconciliación
- el fail-closed Binance para `min_notional > 0` sin precio usable evita un rechazo broker-side evitable en ese caso puntual, pero no reemplaza validaciones adicionales del exchange
- el fail-closed Binance para estado no operativo o sin permiso MARKET usa metadata ya disponible del símbolo; si la metadata no incluye `status`/`contractStatus` u `orderTypes`, la validación no se activa; no reemplaza otras validaciones del exchange ni broker-side guards superiores
- Binance auto-pick live SPOT BUY ahora incluye un guard broker-side por `can_trade` y `USDT free` vs `estimated_notional * 1.02`, pero su cobertura es intencionalmente acotada
- retries y reprocesamientos aún pueden crear duplicados broker-side fuera del flujo Binance auto-pick live endurecido o si no existe `intent_key`
- dry_run paths do not enforce idempotency.

Impact:

Duplicate execution risk exists but is partially mitigated.

---

# 7. Broker Integration Readiness

### Status: **MODERATE**

Strengths:

- broker adapters isolated in runtime layer
- quantity normalization for broker rules
- retry logic for transient errors
- simulated fallback for IBKR

Weaknesses:

- broker order id determinism is only partially covered; hardened Binance live auto-pick uses deterministic `client_order_id` when `intent_key` exists, but legacy/manual flows remain unchanged
- dispatcher hardening is only a contract guard on `_send_binance_test_order`; it blocks direct non-conforming calls without `client_order_id`, but it is not a substitute for higher-level execution controls
- IBKR dispatcher hardening is only a contract guard on `send_ibkr_test_order`; it blocks direct non-conforming calls without `order_ref`, but it is not a substitute for higher-level execution controls
- Binance min-notional hardening is only a fail-closed pre-dispatch guard for missing usable price in that specific case; it is not full exchange-filter coverage
- Binance symbol status and MARKET permission hardening is only a fail-closed pre-dispatch guard using available exchangeInfo metadata; if that metadata is absent the check does not activate; it is not full exchange-filter coverage and does not substitute broker-side guards
- broker-side balance/trading gating is only partially covered; current guard is limited to Binance live SPOT BUY eligible in USDT and is not a general reconciliation layer
- reconciliation logic not centralized
- exposure checks do not validate broker balances directly.

Impact:

Broker integrations are usable but need stronger reconciliation guarantees.

---

# 8. Risk Controls

### Status: **GOOD**

Implemented protections:

- exposure limits
- max open positions
- max symbol quantity
- max notional per exchange
- kill switch
- runtime strategy policies
- exit-plan guards

Additional protection:


X-Idempotency-Key required for real trading


Overall risk control layer is strong.

---

# 9. Observability and Audit

### Status: **GOOD**

System records operational evidence for:

- signal processing
- candidate selection
- execution attempts
- broker responses
- scheduler operations

Audit records are stored through:


AuditLog


Logs provide traceability for trading decisions.

---

# 10. Operational Safety

### Status: **GOOD**

Operational safeguards include:

- kill switch
- safety checklist
- scheduler monitoring
- exposure monitoring
- broker connectivity verification

Operational documentation exists in:


TRADING_SAFETY_CHECKLIST.md


---

# 11. Remaining Production Risks

The following areas represent the most important remaining risks.

### 1. Position concurrency

Concurrent calls to:


POST /positions/open_from_signal


may open duplicate positions without row-level locking.

---

### 2. Broker order idempotency

Broker order identifiers are only partially deterministic.

Hardened Binance live auto-pick now derives `client_order_id` deterministically when `intent_key` exists, but retries outside that flow may still generate multiple broker orders.

---

### 3. Exposure calculation mismatch

Exposure checks use candidate qty while execution uses adjusted qty.

This may produce inconsistent risk evaluation.

---

### 4. Dry-run idempotency gap

Dry-run execution paths do not require idempotency keys.

Repeated requests may execute identical flows.

---

### 5. Scheduler/manual race conditions

Scheduler execution and manual API actions may operate simultaneously.

Exposure checks may therefore evaluate stale data.

Partial mitigation: live auto-pick (`dry_run=false`) now acquires a semantic intent advisory lock (PostgreSQL only, commit 31176d6) before dispatch, preventing two concurrent live calls with the same material intent from both reaching the broker. Residual risk remains for dry-run paths and non-Postgres environments.

---

# 12. Recommended Operational Mode

Until further hardening is implemented, the platform should operate under:

### Conservative execution policy

Recommended configuration:


low max exposure
low position count
dry_run default
limited symbol universe


### Monitoring required

Operators must monitor:

- scheduler activity
- signal lifecycle
- exposure levels
- broker responses.

---

# 13. Overall Production Readiness Score

| Area | Status |
|-----|-----|
Architecture | GOOD |
Trading Engine | MODERATE |
Scheduler | GOOD |
Duplicate Protection | MODERATE |
Broker Integration | MODERATE |
Risk Controls | GOOD |
Observability | GOOD |

Overall readiness:


CONDITIONALLY READY


The system can operate safely under conservative conditions but requires additional hardening for high-frequency or high-capital environments.

---

# 14. Final Statement

The system demonstrates a thoughtful architecture with multiple layers of protection.

However automated trading systems require extremely strong guarantees against duplication, race conditions, and broker inconsistencies.

Before operating significant capital, the following improvements should be prioritized:

- deterministic broker order identifiers
- stronger signal/position locking
- unified exposure calculation
- improved reconciliation mechanisms

Once these areas are addressed, the platform can achieve a high level of production safety.
