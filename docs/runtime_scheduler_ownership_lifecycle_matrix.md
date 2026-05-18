# Scheduler Runtime Ownership Lifecycle Matrix

## Scope

This document defines the scheduler runtime ownership lifecycle states and allowed transitions.

It is documentation only.

It does not implement:
- scheduler loop integration
- ownership enforcement
- takeover
- recovery
- broker mutation
- execution authority

## Authority rules

Runtime DB is the ownership authority.

The scheduler runtime loop remains the only future path allowed to attempt active ownership.

DATA DB never grants runtime authority.

Frontend control plane may observe and request, but may not directly mutate runtime ownership.

## Lifecycle states

| State | Meaning |
|---|---|
| INIT | Runtime process has started but has not attempted ownership. |
| ACQUIRING | Runtime authority path is attempting atomic ownership acquisition. |
| ACTIVE | Runtime owns scheduler authority and may heartbeat, subject to advisory lock and health checks. |
| STALE | Observed heartbeat is stale. This is not takeover authorization. |
| RECOVERING | Reserved future operator-governed recovery state. Not implemented. |
| STOPPING | Runtime is intentionally stopping and should release/clear authority only through a reviewed path. |
| STOPPED | Runtime stopped without active authority. |
| LOST_LOCK | Runtime lost advisory lock or cannot prove lock validity. |
| FAILED | Runtime encountered unrecoverable authority/runtime failure. |
| ZOMBIE_SUSPECTED | Runtime may still be alive while ownership/lock state is inconsistent. |

## Allowed current-phase transitions

Current phase allows only conceptual, documented transitions.

No active scheduler loop transition is implemented yet.

| From | To | Allowed now | Notes |
|---|---:|---:|---|
| INIT | ACQUIRING | Documentation only | Future scheduler authority path only. |
| ACQUIRING | ACTIVE | Documentation only | Requires successful atomic acquisition plus advisory lock validation. |
| ACQUIRING | STOPPED | Documentation only | Acquisition failed safely before active ownership. |
| ACTIVE | LOST_LOCK | Documentation only | Must fail closed. Broker mutation prohibited. |
| ACTIVE | FAILED | Documentation only | Must fail closed. Broker mutation prohibited. |
| ACTIVE | STOPPING | Documentation only | Requires reviewed shutdown path. |
| STOPPING | STOPPED | Documentation only | Requires reviewed ownership release semantics. |
| ACTIVE | STALE | Observational only | Stale does not imply takeover. |
| STALE | ZOMBIE_SUSPECTED | Observational only | Requires operator attention. |
| FAILED | RECOVERING | Not allowed yet | Future explicit design required. |
| STALE | RECOVERING | Not allowed yet | Future explicit design required. |
| ZOMBIE_SUSPECTED | RECOVERING | Not allowed yet | Future explicit design required. |
| RECOVERING | ACTIVE | Not allowed yet | Future explicit design required. |

## Prohibited transitions

The following transitions are prohibited in the current phase:

| From | To | Reason |
|---|---|---|
| STALE | ACTIVE | Stale heartbeat does not grant takeover authority. |
| FAILED | ACTIVE | Failure requires explicit reviewed recovery. |
| LOST_LOCK | ACTIVE | Lock loss must fail closed. |
| ZOMBIE_SUSPECTED | ACTIVE | Zombie ambiguity must fail closed. |
| STOPPED | ACTIVE | Start authority must be separately governed. |
| Any | ACTIVE | Without advisory lock validation. |
| Any | ACTIVE | Without valid ownership row. |
| Any | ACTIVE | From DATA DB state. |
| Any | ACTIVE | From frontend request alone. |

## ACTIVE requirements

A runtime may be considered ACTIVE only when all of the following are true:

- ownership row is complete and valid
- runtime_owner_id is present
- runtime_instance_id is present
- runtime_generation is positive
- runtime_heartbeat_at is present
- advisory lock is currently valid
- runtime process owns the instance identity
- reconciliation is valid
- no LOST_LOCK condition exists
- no FAILED condition exists
- no ZOMBIE_SUSPECTED condition exists

ACTIVE does not by itself authorize broker mutation.

## Execution authority dependency

Execution authority is stricter than ownership authority.

Broker mutation requires at minimum:

- trading_enabled is true
- ownership state is ACTIVE
- advisory lock is valid
- reconciliation is valid
- runtime health is valid
- no LOST_LOCK / FAILED / ZOMBIE_SUSPECTED condition exists
- gateway path is used

This document does not implement execution authority.

## ACQUIRING rules

ACQUIRING must use atomic acquisition only.

Read-then-update acquisition remains prohibited.

ACQUIRING must fail closed if:

- scheduler_runtime_state is missing
- ownership state is partial
- ownership is already present
- atomic update returns no row
- now is timezone-naive
- runtime generation is invalid
- advisory lock cannot be proven valid

## STALE rules

STALE is observational.

STALE must not:
- clear ownership
- overwrite ownership
- increment generation
- imply recovery
- imply takeover
- imply broker mutation is safe

STALE should require operator-visible attention.

## LOST_LOCK rules

LOST_LOCK must fail closed.

When lock validity cannot be proven, runtime authority must be considered invalid.

Future implementation must ensure broker mutation is blocked before, during, and after LOST_LOCK handling.

## ZOMBIE_SUSPECTED rules

ZOMBIE_SUSPECTED means the system cannot safely prove that the previous owner is gone.

It must not be auto-overridden.

Future recovery must be:
- separately documented
- operator-governed
- auditable
- fail-closed by default

## Recovery rules

Recovery is not implemented in the current phase.

Any future recovery path must define:

- who can initiate recovery
- how advisory lock is checked
- how stale owner is proven inactive
- how generation advances
- how ownership is cleared or superseded
- how operator visibility is provided
- how rollback works
- how broker mutation remains blocked until authority is valid

## Frontend boundary

Frontend may display:
- desired_state
- effective_state
- ownership projection
- heartbeat freshness
- stale status
- operator_attention_required
- current lifecycle state

Frontend must not directly:
- acquire ownership
- clear ownership
- perform takeover
- start runtime authority
- grant execution authority
- mutate broker state

## DATA plane boundary

DATA DB may store observations, analytics, snapshots, ranked candidates, and exports.

DATA DB must not:
- define scheduler ownership
- define runtime authority
- define execution authority
- override runtime DB
- infer production users/settings/state

## Current safe next steps

Allowed:
- documentation
- isolated tests
- projection-only lifecycle helpers
- operator-visible read-only projections

Not allowed yet:
- scheduler_runtime_loop.py integration
- active ownership enforcement
- automatic heartbeat loop changes
- takeover
- recovery
- broker mutation
- execution authority enforcement
