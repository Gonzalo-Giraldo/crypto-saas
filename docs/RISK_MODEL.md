# RISK_MODEL.md

## 1. Purpose

This document describes the **risk control model** of the trading platform.

Its goal is to explain how the system prevents:

- unsafe trade execution
- excessive exposure
- duplicate orders
- incorrect sizing
- cross-tenant data leaks
- paper/live execution confusion
- inconsistent balance or position state

Risk control is a fundamental layer of the platform.

---

## 2. Risk Control Philosophy

The platform follows these risk principles:

1. **Fail closed whenever uncertainty exists**
2. **Guard execution before sending orders**
3. **Never assume broker responses are perfect**
4. **Protect balance and position integrity**
5. **Prevent duplicate order execution**
6. **Isolate tenants and users strictly**
7. **Maintain separation between paper and live trading**
8. **Preserve idempotency in critical paths**

Risk checks are layered and occur **before execution**.

---

## 3. Main Risk Entities

The following models participate in risk control:

### Runtime risk state

DailyRiskState

Tracks runtime exposure and daily limits.

---

### Risk configuration

RiskProfileConfig
StrategyRuntimePolicy
RuntimeSetting
UserRiskProfile
UserRiskSettings


These entities define:

- allowed risk levels
- exposure limits
- strategy rules
- runtime configuration

---

### Operational protection

IdempotencyKey
AuditLog


These ensure:

- duplicate execution protection
- audit traceability

---

## 4. Pretrade Risk Checks

Before an order can be generated, the system performs several checks:

### Signal validation

Ensures the signal:

- is authorized
- belongs to the correct tenant/user/account
- has not been processed already

---

### Exposure validation

Checks whether executing the trade would violate:

- user exposure limits
- strategy risk limits
- runtime policies

---

### Balance validation

Ensures:

- balance exists
- balance is sufficient
- balance belongs to correct account
- balance data is recent

---

### Position validation

Ensures:

- positions are consistent
- sell actions do not exceed position size
- position ownership is correct

---

### Broker rule validation

Checks broker-specific constraints:

- precision
- lot size
- minimum order size
- symbol normalization

---

## 5. Execution Guardrails

Execution guardrails prevent unsafe orders.

These controls include:

### Trading controls

Implemented in:

apps/api/app/services/trading_controls.py


Responsibilities:

- tenant trading enable/disable
- runtime safety checks
- execution gating

---

### Risk engine

Implemented in:

apps/api/app/services/risk_engine.py


Responsibilities:

- exposure calculations
- runtime policy checks
- risk validation before execution

---

### Real execution guard

Live execution requires additional validation.

Important rules:

- `dry_run=false` must be explicit
- `X-Idempotency-Key` must exist
- `AUTO_PICK_REAL_GUARD_ENABLED` must allow execution
- allowlists may restrict execution

---

## 6. Paper vs Live Risk Separation

The system enforces strict separation between:

paper trading
live trading


Key control:

dry_run


Default behavior:

dry_run = true


This prevents accidental real execution.

Live execution requires explicit guard conditions.

The system must never mix:

- paper balances
- paper positions
- live balances
- live positions
- paper execution history
- live execution history

---

## 7. Duplicate Execution Protection

Duplicate orders are one of the biggest risks in automated trading.

The platform protects against this using:

### Idempotency keys

X-Idempotency-Key


Used to ensure that repeated requests cannot create duplicate orders.

---

### Controlled retries

Retries must be safe.

Retry logic must not create:

- duplicate orders
- duplicate balance updates
- duplicate position updates

---

### Scheduler safety

The internal scheduler may run repeatedly.

Risk protection includes:

- tenant advisory locks
- idempotent job design
- safe re-entrant execution

---

## 8. Concurrency Risk

The system may have concurrent activity across:

- tenants
- users
- broker accounts
- scheduler jobs
- websocket handlers
- broker callbacks
- retries

Risk mitigation strategies include:

- advisory locks
- idempotency enforcement
- tenant scoping
- explicit order identifiers

Agents must assume concurrency exists.

---

## 9. Broker Execution Risk

Broker interaction introduces additional risks:

- network errors
- delayed responses
- partial fills
- rejected orders
- duplicate execution responses
- inconsistent event ordering

The system mitigates these risks using:

- broker adapters
- execution runtime isolation
- reconciliation processes

Broker adapters include:

apps/worker/app/engine/binance_client.py
apps/worker/app/engine/ibkr_client.py


---

## 10. Balance and Position Integrity

Balance and position state must remain consistent across:

- internal database
- broker state
- user-visible state

Important rules:

- balances must not be reused across accounts
- positions must belong to correct account
- broker state must be reconciled
- internal state must remain consistent

---

## 11. Scheduler Risk

The scheduler runs operational automation.

Responsibilities include:

- signal scanning
- auto-pick execution
- exit logic
- learning updates

Scheduler runs **per tenant** and uses advisory locks.

The system must assume scheduler jobs may run multiple times.

All scheduler operations must be idempotent.

---

## 12. Critical Risk Areas

The highest risk parts of the system include:

### Trading decision logic
- buy decision
- sell decision
- quantity sizing

### Execution dispatch
- order submission
- broker interaction

### State synchronization
- balances
- positions
- executions

### Scheduler concurrency
- repeated execution
- race conditions

### Tenant isolation
- data leakage across tenants

---

## 13. Operational Safety Guidelines

Any change affecting risk-sensitive logic must:

- explain the impact
- identify affected modules
- describe validation steps
- propose rollback strategy

Protected modules include:

apps/api/app/api/ops.py
apps/api/app/main.py
apps/api/app/services/trading_controls.py
apps/api/app/services/risk_engine.py
apps/worker/app/engine/execution_runtime.py


Changes to these areas require extreme caution.

---

## 14. Final Notes

Risk control is a **core system responsibility**, not an optional feature.

Every modification to trading logic must prioritize:

- safety
- correctness
- auditability
- idempotency
- tenant isolation

