# Control Cut Log

## 1. Purpose

This log keeps a short, traceable record of formal control cuts.

It is used to:

- capture stop/continue decisions
- preserve context across iterations
- avoid repeating the same risk discussion
- maintain lightweight governance without heavy process

Only add entries for meaningful Level 2/3 checkpoints or when ambiguity justifies a cut.

---

## 2. How To Use

- append new entries at the top
- keep each entry brief and operational
- include evidence and a clear decision
- record next micro-step only (single reversible action)

Do not turn this into a long narrative.

---

## 3. Standard Entry Template

## [CUT-ID] YYYY-MM-DD - Short Title

- Level: 2 or 3
- Trigger: why cut was needed now
- Scope: files/modules/flows in scope
- Risk reviewed: main failure concern
- Evidence checked: tests/logs/manual checks
- Decision: Continue | Continue with condition | Stop
- Condition (if any): concrete guardrail for next step
- Next micro-step: one reversible action
- Owner: name/role

---

## 4. Entries

## [CUT-2026-03-13-04] 2026-03-13 - Consolidacion Kernel S3 (smoke evidence check)

- Level: 2
- Trigger: need minimal executable evidence before deciding whether to resume kernel hardening
- Scope: kernel hardenings and related tests/docs evidence across test_critical_flows and operational docs
- Risk reviewed: insufficient executable confirmation vs documented hardenings; first-line residuals still open
- Evidence checked: existing targeted tests for gateway/bridge error sanitization and idempotency behavior; docs risk/limitations sections
- Decision: Continue with condition
- Condition (if any): do not add new kernel hardening until targeted smoke checks run in a ready test environment
- Next micro-step: restore test environment dependencies (FastAPI/pytest stack) and run prioritized smoke subset before selecting one next kernel action
- Owner: engineering/codex session

## [CUT-2026-03-13-03] 2026-03-13 - Consolidacion Kernel S2 (operational validation)

- Level: 2
- Trigger: need to validate whether current kernel hardenings are sufficiently settled before adding new hardening
- Scope: evidence and residual-risk ordering across CHANGE_COMMUNICATION_LOG.md, TRADING_RISK_GUARDS.md, and PRODUCTION_READINESS.md
- Risk reviewed: first-line residuals still open (duplicate risk outside hardened lane, post-dispatch error asymmetry, partial exchange-filter coverage)
- Evidence checked: controls implemented list, explicit limitations, and remaining-risks sections in technical docs
- Decision: Continue with condition
- Condition (if any): pause new kernel hardening now; run targeted smoke/evidence check and residual map ordering first
- Next micro-step: execute Consolidation Kernel S3 focused on targeted smoke checks and one ranked recommendation for next action
- Owner: engineering/codex session

## [CUT-2026-03-13-02] 2026-03-13 - Kernel Control Cut #1 (phase checkpoint)

- Level: 2
- Trigger: cumulative kernel hardenings completed; need go/no-go decision for immediate further hardening vs consolidation
- Scope: kernel execution safeguards and post-dispatch behavior documented in CHANGE_COMMUNICATION_LOG.md, TRADING_RISK_GUARDS.md, and PRODUCTION_READINESS.md
- Risk reviewed: residual first-line kernel risks (broker-side duplicate prevention outside hardened flow, partial exchange-filter coverage, error-sanitization asymmetry, dry-run idempotency gap)
- Evidence checked: hardened controls list and residual-risk sections in TRADING_RISK_GUARDS.md and PRODUCTION_READINESS.md, plus latest hardening entries in CHANGE_COMMUNICATION_LOG.md
- Decision: Continue with condition
- Condition (if any): do not open broad redesign; execute one micro-hardening at a time only if it closes a first-line kernel risk with minimal reversible scope
- Next micro-step: pause coding and run short consolidation pass (targeted smoke/evidence review + residual-risk ordering), then decide next single kernel micro-hardening or phase shift
- Owner: engineering/codex session

## [CUT-2026-03-13-01] 2026-03-13 - Binance post-dispatch fallback control

- Level: 2
- Trigger: residual ambiguity after gateway deterministic rejection in Binance dispatch path
- Scope: runtime dispatch fallback behavior in apps/worker/app/engine/execution_runtime.py
- Risk reviewed: second direct dispatch attempt after deterministic upstream rejection
- Evidence checked: runtime error path review, gateway error classification (`gateway_upstream_error status=... code=...`), post-dispatch flow audit in ops
- Decision: Continue with condition
- Condition (if any): allow gateway->direct fallback only for transport/unreachable failures; fail-closed when deterministic gateway rejection is already classified
- Next micro-step: apply minimal guard in `_send_binance_test_order` and re-check no unrelated behavior changes
- Owner: engineering/codex session
