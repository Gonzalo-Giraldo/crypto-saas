# ARCHITECTURE.md

## 1. Purpose

This document provides a high-level architectural map of the repository.

Its goal is to help engineers and AI agents quickly understand:

- how the system is structured
- where the critical trading logic lives
- how tenant isolation works
- how broker execution is organized
- where operational risk is concentrated

This document is descriptive, not normative.  
For hard operational guardrails, always read `AGENTS.md`.

---

## 2. System Overview

This repository implements a **multi-tenant, multi-user, multi-broker trading platform**.

The platform supports:

- authenticated users
- tenant-scoped operations
- signal-driven trading flows
- broker-specific execution
- paper trading and guarded live trading
- embedded scheduler-driven automation
- learning and monitoring components
- operational risk controls
- audit and evidence generation

The system is designed for **controlled trading automation**, not generic web application behavior.

---

## 3. High-Level Architecture

At a high level, the system is composed of these major areas:

### A. API Layer
Handles:
- authentication
- request validation
- signal intake
- position endpoints
- pretrade operations
- auto-pick flows
- operational control endpoints

Main area:
- `apps/api/app/api/`

### B. Core Services Layer
Handles:
- risk logic
- trading controls
- execution rules
- operational checks
- policy/runtime evaluation

Main area:
- `apps/api/app/services/`

### C. Domain Models Layer
Handles:
- persistent data structures
- tenant/user/account-linked state
- signals
- positions
- risk state
- runtime policies
- monitoring/learning records

Main area:
- `apps/api/app/models/`

### D. Scheduler / Runtime Orchestration
Handles:
- internal recurring automation
- per-tenant execution loops
- market monitoring
- auto-pick scheduling
- exit logic
- learning tasks

Main file:
- `apps/api/app/main.py`

### E. Broker Execution Layer
Handles:
- runtime dispatch to brokers
- broker-specific execution behavior
- broker API abstractions
- test-order / guarded execution paths

Main area:
- `apps/worker/app/engine/`

### F. Supporting Runtime / Gateway Components
Handles:
- external broker gateway support
- broker-side connectivity helpers

Main area:
- `apps/binance_gateway/`

---

## 4. Root Architectural Principles

The system is organized around these architectural principles:

1. **Tenant safety first**
2. **Broker behavior is not assumed to be uniform**
3. **Trading execution must be guarded**
4. **Paper and live paths must remain separated**
5. **Critical actions must be auditable**
6. **Idempotency must be preserved in execution paths**
7. **Scheduler-driven automation must remain tenant-safe**
8. **Operational correctness matters more than elegance**

---

## 5. Tenant Isolation Model

The tenant model is **hybrid**.

### Confirmed root tenant source
- `users.tenant_id`

### Tenant propagation
- JWT includes tenant claim: `tid`

### Request validation
Authenticated flows must validate:

- `token.tid == user.tenant_id`

Mismatch must fail closed.

### Scheduler isolation
The embedded scheduler:

- enumerates tenants
- executes work per tenant
- uses **advisory lock per tenant**
- prevents cross-tenant scheduler collisions across replicas

### Kill-switch
Trading enablement is scoped per tenant:

- `trading_enabled:{tenant_id}`

### Important architectural note
Not all domains are tenant-scoped in the same way.

There is a hybrid pattern:

- some areas use explicit `tenant_id`
- some areas remain isolated primarily by `user_id`

Examples confirmed from inspection:
- tenant-oriented: learning / market snapshot style data
- user-oriented: signals / positions / secrets / assignments

This means agents and engineers must not “flatten” tenant behavior into a single simplistic rule without careful review.

---

## 6. Main Domain Entities

### Identity / Security
- `User`
- `UserTwoFactor`
- `RevokedToken`
- `SessionRevocation`

### Trading Core
- `Signal`
- `Position`
- `DailyRiskState`

### Policy / Runtime Control
- `RiskProfileConfig`
- `StrategyRuntimePolicy`
- `RuntimeSetting`
- `StrategyAssignment`
- `UserRiskProfile`
- `UserRiskSettings`

### Execution / Safety / Audit
- `ExchangeSecret`
- `IdempotencyKey`
- `AuditLog`

### Learning / Monitoring
- `LearningDecisionSnapshot`
- `LearningDecisionOutcome`
- `LearningRollupHourly`
- `MarketTrendSnapshot`

These are the main entities agents should understand before proposing structural changes.

---

## 7. Core Operational Modules

The following modules are the architectural center of the platform.

### `apps/api/app/api/ops.py`
This is the main operational core.

It contains or coordinates:
- pretrade flows
- execution preparation
- auto-pick logic
- selection and decision orchestration
- quantity sizing involvement
- guarded execution entry
- audit-related operational flow

This is one of the most sensitive files in the repository.

### `apps/api/app/main.py`
This is the main runtime orchestration file.

It contains or coordinates:
- API startup lifecycle
- embedded scheduler
- per-tenant operational loops
- automation timing
- recurring execution tasks

### `apps/api/app/services/trading_controls.py`
This contains operational trading controls such as:
- kill-switch logic
- exposure-related protections
- execution safeguards
- real-trading controls

### `apps/api/app/services/risk_engine.py`
This contains risk-related logic used in operational decision making.

It is part of the decision support and safety layer.

### `apps/api/app/api/positions.py`
This participates in position-related flows and position-opening behavior from trading signals.

### `apps/worker/app/engine/execution_runtime.py`
This is the broker execution dispatch layer.

It handles:
- runtime order handling
- broker execution entry
- broker-specific operational handoff

### `apps/worker/app/engine/binance_client.py`
Binance-specific runtime adapter behavior.

### `apps/worker/app/engine/ibkr_client.py`
IBKR-specific runtime adapter behavior.

---

## 8. Supported Brokers

Confirmed broker integrations:

- `BINANCE`
- `IBKR`

### Architectural implication
Broker behavior must not be generalized without explicit justification.

Differences may include:
- order models
- state transitions
- quantity precision
- lot sizing
- symbol normalization
- fills behavior
- retry behavior
- streaming events
- reconciliation expectations

Broker-specific logic should remain broker-aware.

---

## 9. Signal and Execution Entry Surfaces

### Manual Signal Flows
- `POST /signals`
- `GET /signals`
- `POST /signals/claim`

### Broker-Specific Pretrade / Auto-Pick Flows
- `POST /ops/execution/pretrade/binance/check`
- `POST /ops/execution/pretrade/binance/scan`
- `POST /ops/execution/pretrade/binance/auto-pick`
- `POST /ops/execution/pretrade/ibkr/check`
- `POST /ops/execution/pretrade/ibkr/scan`
- `POST /ops/execution/pretrade/ibkr/auto-pick`

### Position Flow from Signal
- `POST /positions/open_from_signal`

These entry points form the operational surface for decision-to-execution flows.

---

## 10. High-Level Trading Execution Pipeline

Based on repository inspection, the confirmed execution pipeline is:

1. Pretrade check / scan per broker
2. Trading and exposure controls
3. Idempotency enforcement
4. Auto-pick logic via `_auto_pick_from_scan`
5. Selection, liquidity, breaker, learning, and quantity evaluation
6. If `dry_run=false`, apply real guard and exit-plan guard
7. Send execution to broker runtime
8. Persist or emit audit evidence

### Architectural importance
This pipeline should be treated as an ordered safety chain.

Changes that weaken this sequence are operationally dangerous.

---

## 11. Paper vs Live Trading Model

The system supports both paper and live trading.

### Main control
- `dry_run`

### Default posture
Scheduler and auto-pick behavior are conservative by default.

### Additional safeguards for real execution
When `dry_run=false`:
- `X-Idempotency-Key` is required
- `AUTO_PICK_REAL_GUARD_ENABLED` participates in gating
- allowlists may restrict real execution by:
  - email
  - exchange
  - symbol

### IBKR note
IBKR may operate via:
- paper bridge
- safe simulated fallback

### Architectural rule
Paper and live paths must never be mixed in:
- balances
- positions
- execution history
- routing logic
- adapter selection

---

## 12. Scheduler and Background Automation

The system uses an **embedded scheduler**, not a separate active queue runtime in the currently confirmed local setup.

### Confirmed behavior
The internal scheduler:
- runs inside API lifespan
- executes operational flows per tenant
- drives:
  - market monitoring
  - auto-pick
  - exit logic
  - learning tasks
- uses advisory locks per tenant

### External scheduled operations
Operational automation also exists through GitHub workflows.

### Architectural implication
Concurrency, duplicate execution, and idempotency risks must be evaluated in scheduler-related changes.

---

## 13. Risk Concentration Areas

The highest-risk architectural areas are:

### A. Trading decision core
- buy decision logic
- sell decision logic
- quantity sizing
- balance usage
- position usage

### B. Broker execution
- order submission
- broker dispatch
- response handling
- broker-specific behavior

### C. Reconciliation
- internal vs broker state alignment
- positions
- balances
- order/execution state consistency

### D. Scheduler concurrency
- repeated execution
- overlapping loops
- re-entrant work
- advisory lock correctness

### E. Paper vs live separation
- routing correctness
- control boundary integrity
- history/state isolation

### F. Tenant safety
- tenant scope in API flows
- tenant scope in scheduler flows
- mixed tenant/user domain assumptions

---

## 14. Protected Modules

The following modules are change-controlled and must be treated as protected architecture zones:

- `apps/api/app/api/ops.py`
- `apps/api/app/main.py`
- `apps/api/app/api/deps.py`
- `apps/api/app/routes/auth.py`
- `apps/api/app/services/trading_controls.py`
- `apps/api/app/api/positions.py`
- `apps/api/app/services/risk_engine.py`
- `apps/worker/app/engine/execution_runtime.py`
- `apps/worker/app/engine/binance_client.py`
- `apps/worker/app/engine/ibkr_client.py`

Any modification here has system-wide implications.

---

## 15. Recommended Reading Order for Agents

Before attempting broad analysis, agents should read in this order:

1. `AGENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/TRADING_ENGINE.md`
4. `docs/RISK_MODEL.md`

Then inspect code in this order:

1. `apps/api/app/api/ops.py`
2. `apps/api/app/services/trading_controls.py`
3. `apps/api/app/services/risk_engine.py`
4. `apps/api/app/api/positions.py`
5. `apps/api/app/main.py`
6. `apps/worker/app/engine/execution_runtime.py`
7. broker-specific runtime adapters

This minimizes unnecessary repo-wide scanning and improves consistency of analysis.

---

## 16. Architectural Guidance for Future Work

Future work should preserve:

- hybrid tenant isolation behavior
- broker-specific safety boundaries
- live-execution guardrails
- idempotency in execution paths
- scheduler tenant locks
- paper/live separation
- auditability of critical operations

Future work should avoid:

- flattening tenant behavior without evidence
- generalizing broker logic unsafely
- weakening control sequences in trading flows
- mixing documentation, infra, and core execution changes in the same change set
- introducing broad refactors in protected modules without explicit justification

---

## 17. Final Note

This file is a high-level map of the system.

It is meant to reduce onboarding cost for:
- engineers
- reviewers
- AI agents
- operational auditors

For hard guardrails and required behavior, always defer to:

- `AGENTS.md`
