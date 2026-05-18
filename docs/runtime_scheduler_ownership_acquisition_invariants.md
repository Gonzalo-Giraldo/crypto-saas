# Scheduler Runtime Ownership Acquisition Invariants

## Scope

This document defines the safe acquisition invariants for scheduler runtime ownership.

It is documentation only.

It does not authorize:
- scheduler loop integration
- automatic takeover
- stale recovery
- broker mutation
- execution authority
- trading enablement

## Current phase

P3 ownership acquisition foundation.

The system currently has:
- passive ownership persistence fields
- heartbeat projection
- stale heartbeat evaluation
- ownership projection
- ownership state validator
- atomic acquisition primitive

The atomic primitive is not yet integrated into the active scheduler runtime loop.

## Authority principles

Runtime ownership must be acquired only by the runtime authority path.

A process may not claim execution authority merely because:
- trading_enabled is true
- scheduler thread is alive
- runtime_status reports healthy
- local process state appears active
- DATA DB contains recent observations

Runtime DB remains the authority source.

DATA DB never defines runtime ownership.

## Atomic acquisition invariant

Ownership acquisition must be atomic.

The acquisition operation must succeed only when all ownership fields are empty at the moment of the write:

- runtime_owner_id IS NULL
- runtime_instance_id IS NULL
- runtime_generation IS NULL
- runtime_started_at IS NULL
- runtime_heartbeat_at IS NULL

Any partial ownership state must fail closed.

Any already-owned state must fail closed.

A read-then-update acquisition path is prohibited because it is race-prone.

## Validation invariant

Ownership state is valid only when it is either fully empty or fully complete.

A complete ownership state requires:
- runtime_owner_id
- runtime_instance_id
- runtime_generation
- runtime_heartbeat_at

runtime_generation must be positive.

Partial ownership state is invalid and must not be treated as available.

## Time invariant

Acquisition input time must be timezone-aware.

A naive datetime must be rejected.

Storage adapters may normalize timezone representation depending on backend behavior, but the runtime API boundary must require timezone-aware input.

## Generation invariant

runtime_generation must be positive.

The acquisition primitive does not infer generation.

Any future wrapper that computes next generation must do so explicitly and must preserve atomic acquisition semantics.

## Missing state invariant

If scheduler_runtime_state is missing, acquisition must not create it implicitly.

Missing state must fail closed.

State creation belongs to explicit initialization/migration paths, not runtime acquisition.

## Stale invariant

Stale heartbeat detection alone does not grant takeover authority.

A stale owned row must not be overwritten by the acquisition primitive.

Any future stale recovery must be separately designed, tested, documented, and operator-governed.

## Recovery invariant

Automatic recovery is prohibited in the current phase.

No code may:
- clear ownership because heartbeat is stale
- increment generation as takeover
- replace owner after timeout
- assume LOST_LOCK recovery
- mark zombie process as safe to override

## Scheduler integration invariant

The atomic acquisition primitive must not be connected to scheduler_runtime_loop.py until:

1. acquisition wrapper is reviewed
2. ownership lifecycle states are mapped
3. advisory lock interaction is tested
4. heartbeat lifecycle is tested
5. LOST_LOCK / FAILED / ZOMBIE_SUSPECTED behavior is specified
6. operator-visible projection is confirmed
7. rollback path is clear

## Execution authority invariant

Ownership acquisition does not grant broker mutation authority by itself.

Execution authority requires at minimum:
- trading_enabled is true
- ownership is ACTIVE and valid
- advisory lock is valid
- reconciliation is valid
- runtime health is valid
- no LOST_LOCK / FAILED / ZOMBIE_SUSPECTED condition

This document does not implement execution authority.

## Prohibited behaviors

The following are prohibited:

- read-then-update ownership acquisition
- implicit ownership takeover
- implicit state creation
- clearing ownership on stale heartbeat
- broker mutation based only on trading_enabled
- scheduler start/stop based only on frontend control
- DATA DB authority over runtime state
- local Docker DB inference for production state
- modifying financial logic as part of ownership acquisition

## Current safe next steps

Allowed:
- add documentation
- add tests around isolated primitives
- add wrapper only if it delegates to atomic acquisition
- keep scheduler loop disconnected

Not allowed yet:
- runtime loop integration
- active heartbeat loop changes
- takeover
- recovery
- broker mutation
- execution authority enforcement
