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

## [CUT-2026-03-13-06] 2026-03-13 - Priorización de fases: entorno / kernel / constantes

- Level: 2
- Trigger: need explicit work-phase ordering to avoid dispersion across test environment, kernel hardening, and constants cleanup
- Scope: project priorities and sequencing for next 3 weeks across three work streams (smoke subset, kernel modulación, constants audit)
- Risk reviewed: risk of mixing incompatible work streams simultaneously; risk of deferring critical validation capability
- Evidence checked: CONTROL_CUT_LOG.md (5 prior cuts complete), ENGINEERING_AUDIT_AND_CONTROL_POLICY.md (governance model exists), DOMAIN_CONSTANTS_AUDIT.md (analysis complete, no code changes ready), CHANGE_COMMUNICATION_LOG.md (8 hardenings documented, residuals mapped)
- Decision: Continue with explicit phase ordering
- Conditions:
  1. Phase 1 (Prioridad 1): Entorno de pruebas / smoke subset — COMIENCE INMEDIATAMENTE. Blocker para fases 2 y 3. Acción: fix Python 3.11 environment (local OR Docker), ejecutar 5 smoke checks prioritarios, documentar en SMOKE_VALIDATION_RESULTS.md. Timeline: 1-2 horas
  2. Phase 2 (Prioridad 2): Modulación del kernel — COMIENCE DESPUÉS QUE SMOKE ESTÉ VALIDADA. Continuidad lógica post-consolidación S3. Acción: 1 micro-hardening que cierre residual prioridad-1 (duplicado broker-side, error asymmetry, o partial exchange coverage). Timeline: 3-5 horas post-smoke
  3. Phase 3 (Prioridad 3): Limpieza / constantes — BACKLOG CONTROLADO. Postergado a 1-2 semanas post-kernel. Acción: arquitectura decide sobre puntos C/D (no ready today), ejecutar Grupo B (simple) solo si arquitectura aprueba post-kernel. Timeline: decision + grouped execution post-kernel
- Ordering rationale: Phase 1 is pure blocker (no validation capability without tests). Phase 2 follows logically (consolidation S3 done, residuals mapped, microhardening pattern proven). Phase 3 is orthogonal (analysis complete, points C/D not ready for code, can wait 2 weeks without context loss)
- What NOT to mix: (a) do not mix smoke + kernel changes in parallel; (b) do not mix kernel + constants changes simultaneously; (c) do not treat constants{B,C,D} as single phase (are separate groups with different readiness levels)
- Next micro-step: execute Phase 1 immediately (restore Python 3.11 test runtime and run smoke subset)
- Owner: engineering/codex session

---

## [CUT-2026-03-13-05] 2026-03-13 - Entorno de pruebas + smoke subset prioritario (habilitacion)

- Level: 2
- Trigger: need executable evidence before any new kernel hardening
- Scope: test environment readiness and prioritized kernel smoke subset execution capability
- Risk reviewed: inability to validate hardened behavior due runtime/tooling blockers
- Evidence checked: local venv dependency install, pytest startup error under Python 3.9, container-based fallback attempt blocked by Docker daemon not running
- Decision: Continue with condition
- Condition (if any): no new kernel hardening until Python 3.11-capable test run is available and smoke subset is executed
- Next micro-step: fix runtime layer first (use Python 3.11 interpreter or enable Docker daemon), then run prioritized smoke checks in order
- Owner: engineering/codex session

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
