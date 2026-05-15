# Runtime Trailing Operational Invariants

## Scope

This document defines operational invariants for Binance Futures trailing stop protection runtime.

The purpose is not to define trading math or business strategy.

The purpose is to preserve safe, auditable, fail-closed dynamic protection for real-money execution.

## Non-goals

- No change to trading math.
- No change to risk logic.
- No change to SL/TP policy.
- No scheduler activation.
- No automatic retry.
- No cross-worker takeover.
- No optimistic exchange assumptions.

## Authority invariants

| Invariant | Enforcement |
|---|---|
| No trailing replacement without ACTIVE transition claim | runtime gate |
| No protected batch reevaluation without claim acquisition | batch runner |
| No authority propagation gaps | runner -> gate -> orchestrator -> primitive |
| No cross-owner claim completion | claim service |
| UNKNOWN claim state is not authority | claim recovery policy |

## Reconciliation invariants

| Invariant | Enforcement |
|---|---|
| UNKNOWN protection blocks mutation | runtime gate |
| Non-PROTECTED state blocks mutation | runtime gate |
| Missing ACTIVE SL evidence blocks mutation | runtime gate |
| Malformed replacement SL status blocks mutation | replacement primitive |

## Mutation truthfulness invariants

| Invariant | Enforcement |
|---|---|
| No `replaced` without new SL ACTIVE evidence | replacement primitive |
| Ambiguous old SL cancel does not return `replaced` | replacement primitive |
| Cancel ambiguity returns `replacement_pending_cleanup` | replacement primitive |
| Non-favorable SL replacement is blocked | replacement primitive |

## Lifecycle invariants

| Invariant | Enforcement |
|---|---|
| Replacement success maps to FINALIZED | batch runner |
| Noop maps to RELEASED | batch runner |
| Blocked/failed result maps to ABANDONED | batch runner |
| Exception after claim attempts ABANDONED | batch runner |
| Cleanup failure is surfaced, not swallowed | batch runner |
| Lifecycle failure never becomes silent success | batch runner |

## Recovery invariants

| Invariant | Enforcement |
|---|---|
| Stale claim alone does not authorize mutation | claim service |
| UNKNOWN staleness blocks recovery | claim service |
| Different owner cannot recover stale claim | claim service |
| Same owner stale recovery is only a predicate, not automatic execution | claim service |

## Scheduler prerequisites

Scheduler must not be enabled until these are explicitly reviewed:

| Prerequisite | Status |
|---|---|
| restart reconciliation semantics | pending |
| stale claim recovery procedure | pending |
| manual governance for pending cleanup | pending |
| duplicate scheduler overlap prevention | pending |
| post-crash exchange reconciliation | pending |
| production kill switch review | pending |

## Current invariant test coverage

| Area | Test file |
|---|---|
| claim service | `tests/services/test_binance_exit_protection_transition_claim_service.py` |
| replacement primitive | `tests/services/test_binance_exit_stop_loss_replacement.py` |
| runtime gate | `tests/services/test_binance_trailing_stop_runtime_gate.py` |
| reevaluation runner | `tests/services/test_binance_protected_position_reevaluation_runner.py` |
| trailing orchestrator | `tests/services/test_binance_trailing_stop_orchestrator.py` |
| batch reevaluation | `tests/services/test_binance_protected_position_batch_reevaluation_runner.py` |

## Release guardrail

A production scheduler must not be enabled merely because tests pass.

Before scheduler activation, runtime must demonstrate:

- deterministic startup behavior;
- reconciliation before mutation;
- no blind retry after stale claim;
- no automatic takeover;
- explicit handling for `replacement_pending_cleanup`;
- documented manual intervention path;
- operator-visible audit trail.
