# Trading Decision Engine

## 1. Purpose of This Document

This document describes how the platform decides:

- whether to trade
- what side to trade (BUY or SELL)
- what candidate to select
- what quantity to trade
- whether the trade is allowed to proceed

The goal is to document the **actual current behavior of the trading engine**, based on code in:

apps/api/app/api/ops.py  
apps/api/app/services/trading_controls.py  
apps/api/app/services/risk_engine.py  
apps/api/app/api/positions.py  
apps/worker/app/engine/execution_runtime.py  

This document does not propose redesigns.  
It describes the **existing decision architecture**.

---

# 2. High-Level Decision Pipeline

The trading decision pipeline follows this order:

1. Signal or candidate ingestion
2. Pretrade evaluation
3. Exposure validation
4. Strategy checks
5. Candidate scoring
6. Liquidity classification
7. Candidate selection (auto-pick)
8. Quantity sizing
9. Execution guards
10. Broker dispatch

Each step acts as a **safety gate**.

---

# 3. Signal Entry Points

Signals can enter the system from four groups of endpoints.

### Manual signals


POST /signals
GET /signals
POST /signals/claim


Signals are created with status:


CREATED


Claiming signals transitions them to:


EXECUTING


---

### Broker pretrade endpoints

#### Binance


POST /ops/execution/pretrade/binance/check
POST /ops/execution/pretrade/binance/scan
POST /ops/execution/pretrade/binance/auto-pick


#### IBKR


POST /ops/execution/pretrade/ibkr/check
POST /ops/execution/pretrade/ibkr/scan
POST /ops/execution/pretrade/ibkr/auto-pick


These endpoints allow external systems or scanners to submit candidates for evaluation.

---

### Position creation


POST /positions/open_from_signal


This endpoint converts a validated signal into an internal position record.

---

# 4. Candidate Universe Construction

The trading engine evaluates candidates built from one of two sources:

### External candidate list

Provided in request payloads to the scan/auto-pick endpoints.

### Internal universe generator

Function:


_build_auto_pick_universe()


This function builds a list of potential trade candidates.

Default quantities:

| Broker | Default qty |
|------|------|
| Binance | 0.01 |
| IBKR | 1.0 |

These values are seed quantities and are later adjusted during sizing.

---

# 5. Pretrade Evaluation

Each candidate passes through:


_evaluate_pretrade_for_user()


This function evaluates:

- strategy policy
- risk limits
- daily risk state
- exposure rules
- cooldown rules
- user risk profile

If any of these checks fail, the candidate is rejected.

---

# 6. Exposure Validation

Exposure checks occur in:


trading_controls.assert_exposure_limits()


Exposure is calculated from:


Position


records where:


status == OPEN


Exposure metrics include:

- open quantity per symbol
- open notional per exchange
- total open positions
- daily trade counts

If exposure limits are exceeded, the candidate is rejected.

---

# 7. Candidate Scoring

Candidates are scored using:


_pretrade_scores()


Score calculation includes:

- trend alignment
- signal timing
- reward/risk ratio
- market regime
- strategy-specific rules

Candidates must exceed:


runtime_policy.min_score_pct


to remain eligible.

---

# 8. Liquidity Classification

Function:


_classify_liquidity_state()


Inputs include:

- spread_bps
- slippage_bps
- max_spread_bps
- max_slippage_bps
- candidate score

Liquidity states:

| State | Multiplier | Meaning |
|------|------|------|
| green | 1.0 | strong liquidity |
| gray | 0.5 | acceptable but reduced |
| red | 0.0 | unsafe to trade |

If liquidity is red, the candidate is rejected.

---

# 9. Candidate Selection (Auto-Pick)

Core decision function:


_auto_pick_from_scan()


Steps:

1. filter eligible candidates
2. sort by score
3. choose highest scoring candidate


selected = score_eligible[0]


Side selection:


selected_side = selected["side"]


Possible values:


BUY
SELL


---

# 10. Additional SELL Constraints

SELL trades require stricter liquidity.

Condition:


if selected_side == "SELL" and liquidity_state != "green"


SELL trades with gray liquidity are rejected.

BUY trades may proceed with gray liquidity.

---

# 11. Quantity Sizing

Quantity sizing occurs inside:


_auto_pick_from_scan()


Formula:


selected_qty = candidate_qty * size_multiplier


Where:


size_multiplier


comes from the liquidity classifier.

---

### Liquidity multipliers

| Liquidity | Multiplier |
|------|------|
| green | 1.0 |
| gray | 0.5 |
| red | 0.0 |

---

### SELL adjustment

SELL trades apply an additional reduction:


selected_qty = selected_qty * 0.35


This reflects a conservative short position sizing rule.

---

# 12. Broker Quantity Normalization

Before sending an order to the broker, quantities are normalized.

Example:


prepare_binance_market_order_quantity()


Normalization includes:

- step size
- minimum quantity
- minimum notional
- precision rules

---

# 13. Execution Guards

Before dispatching an order, additional protections apply.

### Real trading guard

If:


dry_run = false


the request must include:


X-Idempotency-Key


Additional checks include:

- email allowlist
- exchange allowlist
- symbol allowlist

---

### Exit-plan guard

If enabled, a trade must also produce:

- minimum reward/risk ratio
- ATR-based exit plan

Otherwise the trade is rejected.

---

# 14. Broker Dispatch

Orders are dispatched via:


execution_runtime.py


Key functions:


execute_binance_test_order_for_user()
execute_ibkr_test_order_for_user()


These functions:

- prepare credentials
- normalize quantity
- generate client order identifiers
- send test orders
- record audit logs

---

# 15. Audit and Logging

Every decision step produces audit evidence.

Examples include:

- pretrade evaluation results
- candidate selection
- sizing output
- execution outcome
- broker responses

Audit records are stored using:


AuditLog


---

# 16. Current Model Characteristics

The decision engine uses a hybrid model composed of:

- strategy policy checks
- scoring heuristics
- liquidity gating
- exposure limits
- conservative SELL adjustments

The sizing model is therefore **heuristic rather than purely capital-based**.

---

# 17. Known Structural Characteristics

Important architectural observations:

1. candidate quantities originate from universe generation or input payloads
2. liquidity multipliers adjust trade size
3. SELL trades are reduced via fixed multiplier
4. exposure validation occurs before final sizing
5. broker normalization may further adjust final quantities

---

# 18. Design Intent

The engine is designed to:

- prevent unsafe trades
- reduce exposure risk
- enforce strategy discipline
- allow automated candidate selection
- provide auditable trading decisions

Every decision must pass multiple independent validation layers.

---

# 19. Operational Safety Philosophy

The system follows a layered defense model:

1. candidate validation
2. strategy validation
3. exposure validation
4. liquidity validation
5. quantity adjustment
6. execution guardrails
7. broker dispatch

If any layer fails, the trade is rejected.

---

# 20. Final Note

The trading decision engine is the most critical part of the system.

Changes affecting:

- scoring
- liquidity classification
- sizing logic
- exposure limits
- broker execution

must be evaluated carefully to avoid unintended trading behavior.
