# Engineering Audit and Control Policy

## 1. Purpose

This policy defines a lightweight way to decide when to pause and run a control cut (checkpoint review) during development.

It is designed to:

- protect stability and correctness
- preserve delivery speed
- avoid unnecessary bureaucracy
- keep system-level visibility while shipping small increments

This is a practical operating guide, not a heavy approval workflow.

---

## 2. Scope

Applies to all development work in this repository:

- API, worker, scheduler, adapters, gateway, data models, and docs
- functional changes, risk controls, integrations, and operational behavior
- technical decisions that can affect safety, reliability, isolation, or maintainability

It is not limited to kernel hardening.

---

## 3. Principles

1. Minimal sufficient control
2. Risk-based depth (not one-size-fits-all)
3. Small reversible changes first
4. Evidence over opinion
5. Fast stop/continue decisions
6. Keep product context visible at all times

---

## 4. Change Levels

## Level 1 - Small Change

Typical profile:

- small local fix, docs-only, low-risk guardrail text, harmless refactor with no behavior shift
- narrow scope, low blast radius, easy rollback

Default control mode:

- no formal control cut required
- short self-check is enough

Expected artifacts:

- concise change note in PR/commit
- tests or smoke check when relevant

## Level 2 - Sensitive Change

Typical profile:

- affects execution paths, auth boundaries, tenant/account scoping, broker error handling, risk checks, idempotency, scheduler interactions, or data integrity logic
- still limited in scope, but operationally meaningful

Default control mode:

- lightweight formal control cut required
- one short checkpoint before merge or before next sensitive step

Expected artifacts:

- explicit risk note
- validation evidence
- log entry in CONTROL_CUT_LOG.md

## Level 3 - Structural Change

Typical profile:

- multi-module behavior changes, architecture shifts, contract changes, schema-sensitive work, or sequence changes in protected flows
- moderate/high blast radius or difficult rollback

Default control mode:

- formal control cut required before implementation and before release
- may require staged rollout and rollback rehearsal

Expected artifacts:

- clear decision record
- validation plan and outcome
- log entry in CONTROL_CUT_LOG.md

---

## 5. When a Formal Control Cut Is Required

Run a formal control cut when at least one condition is true:

- change is Level 2 or Level 3
- behavior changes in protected operational flows
- uncertainty exists about failure mode, race risk, or scope boundaries
- multiple hardenings are chaining and cumulative risk is rising
- ambiguity exists on whether to continue in the same branch of work

---

## 6. When Formal Cut Is Not Required

Formal cut is optional when all conditions hold:

- change is Level 1
- low-risk, local, and reversible
- no protected flow semantics changed
- validation is straightforward and already executed

In these cases, continue with micro-change plus concise review.

---

## 7. Practical Joint Evaluation Structure (Control Cut)

Use this compact structure only when it adds real value (Level 2/3 or ambiguity):

1. Change objective (one sentence)
2. Scope touched (files/modules/flows)
3. Operational risk (what can fail)
4. Evidence (tests, logs, traces, manual checks)
5. Residual exposure (what remains open)
6. Stop/Continue decision
7. Next micro-step (single reversible action)

Timebox target: 10-20 minutes.

If this structure does not add decision quality for a Level 1 change, skip formal cut.

---

## 8. Stop / Continue Criteria

## Continue if

- objective remains clear
- residual risk is known and acceptable for current step
- rollback is available
- evidence supports expected behavior
- next step remains small and reversible

## Stop if

- unexpected behavior appears in protected flows
- side effects exceed declared scope
- rollback is unclear
- evidence is contradictory or insufficient
- cumulative changes reduce clarity of system state

When stop is triggered, run a control cut before more coding.

---

## 9. Avoid Losing the Forest for the Trees

To preserve system-level visibility:

- alternate rhythm: micro-change -> review -> control cut (when needed) -> continue decision
- do not chain many sensitive edits without a checkpoint
- keep explicit notes of what was intentionally not changed
- separate tactical fixes from structural discussions
- prefer one-risk-at-a-time progression

Practical cadence:

- Level 1: review every 3-5 micro-changes
- Level 2: cut at each meaningful behavior shift
- Level 3: cut before implementation and before release

---

## 10. Relationship With Technical Docs

This policy complements and does not replace system technical docs, especially:

- ARCHITECTURE.md
- TRADING_ENGINE.md
- TRADING_RISK_GUARDS.md
- PRODUCTION_READINESS.md
- SCHEDULER_AND_CONCURRENCY_MODEL.md
- CHANGE_COMMUNICATION_LOG.md

Use CONTROL_CUT_LOG.md as the concise trace of cut decisions.

---

## 11. Lightweight Governance Rules

- Keep control cuts short and evidence-driven
- Avoid mandatory templates for every minor change
- Do not block delivery with ceremony
- Escalate control depth only when risk requires it
- Favor clarity, reversibility, and operational safety
