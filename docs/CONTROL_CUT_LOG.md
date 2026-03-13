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
