# Auto-pick Runtime Semantic Gaps

## Purpose

Document semantic differences between:

- legacy runtime orchestrator path
- shared deterministic evaluation engine

Runtime migration MUST NOT occur until every gap is reviewed explicitly.

## Known semantic gaps

### 1. No selection reason naming

Legacy runtime:
- no_symbols

Evaluation engine:
- no_candidate_symbols

Risk:
- downstream semantic dependency unknown

---

### 2. Rejected candidate evidence

Legacy runtime:
- silently skips many failures

Evaluation engine:
- persists rejected_candidates evidence

Risk:
- operational observability changes
- frontend assumptions unknown

---

### 3. Exception semantics

Legacy runtime:
- broad silent continue

Evaluation engine:
- classified rejection evidence

Risk:
- runtime monitoring behavior changes

---

### 4. Side normalization timing

Legacy runtime:
- validates BUY/SELL after scoring

Evaluation engine:
- currently trusts score payload more directly

Risk:
- ranking/filter parity divergence

---

### 5. Runtime timestamps

Legacy runtime:
- owns started_at / finished_at

Evaluation engine:
- currently pure evaluation only

Risk:
- lifecycle ownership ambiguity

---

### 6. Runtime adapter ownership

Current:
- orchestrator owns broker fetch + projection

Target:
- runtime adapter layer around shared engine

Risk:
- accidental runtime semantic migration

---

### 7. Ranking parity edge cases

Not yet audited:
- NaN
- None
- invalid score coercion
- stable ordering ties
- side casing

Migration blocked until audited.
