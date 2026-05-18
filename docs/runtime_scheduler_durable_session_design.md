# Runtime Scheduler Durable Session Design

## Scope

This document defines the future durable runtime session model for the scheduler.

It is design documentation only.

It does not implement:
- scheduler loop integration
- durable lock session
- takeover
- recovery
- execution authority
- broker mutation

## Problem

The scheduler currently has:

- tick-scoped advisory lock
- durable ownership substrate
- lifecycle projection
- runtime status observability

It does not yet have a fully governed durable runtime session.

A durable runtime session is required before ACTIVE ownership can be used for runtime authority or execution authority.

## Design goal

Create a runtime authority model that can safely answer:

- which runtime instance owns scheduler authority
- whether that owner is alive
- whether lock/session authority is still valid
- whether the owner lost lock authority
- whether another process may acquire authority
- whether operator attention is required

The design must fail closed under uncertainty.

## Non-goals

This design does not attempt to:

- change auto-pick scoring
- change selection semantics
- change risk logic
- change execution logic
- change broker behavior
- enable trading
- implement automatic takeover
- implement recovery
- implement execution authority

## Required authority sources

A future durable runtime session must reconcile three sources:

1. Runtime DB ownership row
2. Advisory lock/session authority
3. Local runtime process/thread state

No single source is sufficient alone.

## Runtime DB ownership row

Runtime DB stores durable ownership metadata:

- scheduler_name
- runtime_owner_id
- runtime_instance_id
- runtime_generation
- runtime_started_at
- runtime_heartbeat_at

This row is durable and observable.

It is not enough by itself to prove current authority.

## Advisory lock/session authority

A future durable runtime authority implementation must use a lock/session model whose lifetime can be reasoned about.

The current tick-scoped advisory lock is not enough.

A future design may use:

- a dedicated PostgreSQL advisory lock connection held for the authority session
- or another explicitly designed durable coordination primitive

Requirements:

- lock ownership must be tied to runtime authority lifecycle
- lock loss must be detectable
- lock ambiguity must fail closed
- lock release must be explicit when graceful
- lock release must be automatic on connection/process death if using PostgreSQL advisory locks

## Local runtime process/thread state

Local state can indicate whether a runtime thread is alive.

It is not durable.

It must not override Runtime DB.

It must not override advisory lock/session authority.

It may be used as supporting evidence for local observability.

## Session identity

A durable runtime session must have a stable identity for the lifetime of that session.

Required identity components:

- runtime_owner_id
- runtime_instance_id
- runtime_generation

Future implementation may also add:

- runtime_session_id
- runtime_epoch
- fencing_token

No broker mutation may rely on local thread identity alone.

## Fencing

Runtime generation is the minimum existing fencing primitive.

Future execution authority must reject stale actors whose generation does not match the current durable ownership row.

Any future broker mutation path must verify the current generation before mutation.

## Acquisition sequence

A future safe acquisition sequence must be designed as:

1. Build runtime identity
2. Acquire durable advisory/session authority
3. Atomically acquire runtime DB ownership
4. Start heartbeat loop
5. Confirm ownership row still matches local identity
6. Enter ACTIVE projection only after all authority sources agree

If any step fails, acquisition must fail closed.

## Ordering constraint

The advisory/session lock should be acquired before DB ownership is marked ACTIVE.

Reason:

- if DB ownership is acquired first and lock acquisition fails, the system may leave a misleading owner row
- if lock is acquired first and DB acquisition fails, the process can release lock safely without claiming durable ownership

This ordering may be revisited only with explicit tests and documented rollback semantics.

## Heartbeat semantics

Heartbeat must be written only by the current owner.

A heartbeat update must require:

- scheduler_name matches
- runtime_owner_id matches
- runtime_instance_id matches
- runtime_generation matches

Heartbeat update must fail closed if the row no longer matches.

A failed heartbeat must transition local authority to LOST_LOCK or FAILED in future implementation.

## Lock loss semantics

If advisory/session authority is lost or cannot be proven:

- broker mutation must be blocked
- heartbeat must stop or fail closed
- lifecycle must not remain ACTIVE
- operator_attention_required must become true
- future implementation must project LOST_LOCK or FAILED

Lock ambiguity must be treated as lock loss.

## Split-brain prevention

The system must prevent or fail closed on:

- two processes claiming same scheduler
- stale process continuing after newer generation
- process with lock but no DB ownership
- process with DB ownership but no lock
- process with stale generation
- process with local thread alive but stale heartbeat
- process with frontend requested state but no authority

## Recovery

Recovery is not automatic in the current design.

Future recovery must define:

- who can initiate it
- what evidence proves previous owner is gone
- how lock/session authority is verified
- how ownership is cleared or superseded
- how generation advances
- how audit trail is recorded
- how execution remains blocked until authority is valid

## Graceful shutdown

A future graceful shutdown path must:

1. stop accepting authority-dependent work
2. stop broker mutation eligibility
3. stop heartbeat loop
4. release DB ownership only if identity still matches
5. release advisory/session lock
6. project STOPPED or STOPPING safely

Shutdown failure must not create false ACTIVE state.

## Abrupt restart

On abrupt process/container restart:

- PostgreSQL advisory lock connection should be released automatically if connection dies
- DB ownership row may remain present
- heartbeat eventually becomes stale
- stale does not authorize takeover
- operator-governed recovery is required until recovery semantics exist

## Runtime status projection

Runtime status may expose:

- ownership lifecycle state
- ownership validity
- heartbeat freshness
- operator attention
- durable session readiness
- lock model readiness
- known gaps

Runtime status must not grant authority.

## Frontend boundary

Frontend may observe and request.

Frontend must not directly:

- acquire ownership
- clear ownership
- force takeover
- grant ACTIVE authority
- grant execution authority
- mutate broker state

## DATA plane boundary

DATA DB never grants runtime authority.

DATA DB never resolves ownership ambiguity.

DATA DB never proves execution authority.

## Execution authority dependency

P5 execution authority requires this durable session model to be implemented and verified.

Until then, ownership projection must remain observational.

## Required tests before implementation

Before scheduler integration, future implementation must include tests for:

1. lock acquired then DB ownership acquired
2. lock acquisition fails, no DB ownership written
3. DB atomic acquisition fails, lock released
4. heartbeat succeeds only with matching identity
5. heartbeat fails on stale generation
6. lock loss blocks ACTIVE projection
7. stale heartbeat does not grant takeover
8. local live thread without DB ownership is not ACTIVE
9. DB ownership without lock is not ACTIVE
10. graceful shutdown clears ownership only if identity matches
11. stale owner cannot be overwritten without recovery path
12. recovery path remains disabled unless explicitly implemented

## Current conclusion

The current system has enough substrate to design durable runtime sessions.

It does not yet have a fully governed durable runtime session.

Therefore:

- ACTIVE ownership must remain projection-only
- runtime status must remain observational
- scheduler loop integration must wait
- execution authority must remain blocked by design

## Current implementation progress

The current code now includes observability-only runtime session foundations:

- stable local runtime session identity
- local identity reconciliation projection
- generation reconciliation projection
- fail-closed runtime session authority evaluation
- fail-closed advisory session evaluation
- runtime advisory session state holder
- separate advisory lock keys for tick overlap and future runtime session authority

These pieces do not implement durable runtime authority yet.

## Current advisory lock separation

The scheduler tick overlap lock remains separate from future durable runtime session authority.

Current known lock keys:

- scheduler tick overlap lock: 887731
- future runtime session advisory lock: 887732

The tick overlap lock must not be used as proof of durable runtime authority.

The runtime session advisory lock key is reserved for future durable session work and is not yet integrated into the scheduler loop.

## Current runtime status truth

Runtime status may expose:

- local runtime owner identity
- local runtime instance identity
- local identity reconciliation
- generation reconciliation projection
- advisory session projection
- session authority projection

These projections are observability-only.

They must not be used as broker mutation authority.

Until durable advisory/session authority, generation fencing, heartbeat CAS, and reconciliation are fully implemented, runtime session authority must remain fail-closed.

## Current remaining blocking gaps

The following remain blocking before scheduler authority enforcement:

1. durable advisory/session lock acquisition
2. durable advisory/session lock validation
3. durable advisory/session lock release
4. owner-only heartbeat CAS
5. generation/fencing reconciliation
6. LOST_LOCK runtime projection
7. graceful shutdown release semantics
8. explicit recovery-disabled behavior
9. scheduler loop integration
10. execution authority gating
