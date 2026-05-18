# Runtime Scheduler LOST_LOCK Semantics

## Scope

This document defines future LOST_LOCK semantics for scheduler runtime authority.

It is documentation only.

It does not implement:
- durable advisory/session lock
- scheduler loop integration
- lock loss detection
- lifecycle transition logic
- recovery
- takeover
- execution authority
- broker mutation

## Current truth

The system does not currently have a fully governed durable runtime session.

Current lifecycle projection can report ACTIVE when durable ownership metadata is valid and heartbeat is fresh.

That ACTIVE state is observability-only.

It does not prove:
- durable advisory/session lock authority
- local runtime process authority
- ownership-to-lock reconciliation
- execution authority

## LOST_LOCK meaning

LOST_LOCK is a future runtime authority state.

It must mean that a runtime instance previously believed to hold authority can no longer prove advisory/session authority.

LOST_LOCK must not be inferred from ownership row alone.

LOST_LOCK must not be inferred from stale heartbeat alone.

LOST_LOCK requires explicit future reconciliation evidence.

## Required future evidence

A future implementation may project LOST_LOCK only when it can evaluate at least:

1. runtime DB ownership row
2. durable advisory/session lock authority
3. local runtime identity
4. runtime generation/fencing token
5. heartbeat ownership state
6. reconciliation result

If lock/session authority is lost, ambiguous, expired, disconnected, or unverifiable, authority must fail closed.

## ACTIVE is not lock authority

Current ACTIVE lifecycle projection only means:

- ownership substrate is structurally valid
- ownership is present
- heartbeat is not stale

It does not mean lock/session authority exists.

It must not be used to permit broker mutation.

## STALE is not LOST_LOCK

STALE means heartbeat is stale.

STALE does not prove:
- the process is dead
- the advisory/session lock was lost
- takeover is safe
- recovery is authorized

STALE may require operator attention, but it is not sufficient evidence for automatic recovery.

## Broker mutation rule

Broker mutation must remain prohibited unless future execution authority validates:

- trading_enabled is true
- durable ownership is valid
- durable advisory/session lock authority is valid
- runtime identity matches ownership row
- generation/fencing token matches
- reconciliation is valid
- runtime health is valid
- no LOST_LOCK condition exists
- no FAILED condition exists
- no ZOMBIE_SUSPECTED condition exists
- gateway path is used

LOST_LOCK must block broker mutation.

## Recovery rule

LOST_LOCK must not trigger automatic recovery in the current design.

Future recovery must be explicitly designed, tested, operator-governed, auditable, and fail-closed.

## Non-goals

This document does not define:
- exact lock implementation
- takeover sequence
- recovery workflow
- frontend controls
- execution authority implementation

Those must be introduced separately with tests before runtime integration.
