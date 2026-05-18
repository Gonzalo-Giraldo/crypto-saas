# Runtime Scheduler Session Durability Boundary

## Scope

This document defines the current boundary between:

- scheduler tick concurrency locks
- semantic intent locks
- durable runtime ownership substrate
- fully governed durable runtime session

It is documentation only.

It does not implement:
- scheduler loop integration
- durable lock session
- takeover
- recovery
- execution authority
- broker mutation

## Current truth

The system currently has a durable ownership substrate.

It does not yet have a fully governed durable runtime session.

## What exists today

The current implementation includes:

- scheduler_runtime_state durable table
- runtime_owner_id
- runtime_instance_id
- runtime_generation
- runtime_started_at
- runtime_heartbeat_at
- ownership validator
- atomic ownership acquisition primitive
- safe acquisition service
- heartbeat stale evaluator
- lifecycle projection
- runtime status ownership projection

These pieces allow the system to represent and observe runtime ownership state.

They do not yet make runtime authority fully governed or durable.

## What does not exist yet

The system does not yet have:

- durable runtime session authority
- dedicated runtime advisory lock session
- ownership-to-lock reconciliation
- active heartbeat authority loop
- durable ACTIVE enforcement
- LOST_LOCK runtime behavior
- ZOMBIE_SUSPECTED runtime behavior
- ownership release semantics
- stale recovery semantics
- operator-governed takeover
- fencing/session epoch enforcement
- execution authority gating based on ownership

## Lock layers

There are currently distinct lock/concurrency concepts.

They must not be treated as equivalent.

## 1. Tick overlap lock

The scheduler uses a PostgreSQL advisory lock around a scheduler tick.

Purpose:

- prevent overlapping scheduler tick execution across replicas

Current semantics:

- lock is acquired before a tick
- tick runs
- lock is released after the tick
- lock lifetime is tick-scoped

This is not durable runtime ownership.

It must not be used as proof of ACTIVE runtime authority.

## 2. Semantic intent lock

Historical hardening introduced semantic advisory locking around intent-level operations.

Purpose:

- prevent duplicate or conflicting operational intent execution
- scope by semantic business identity such as tenant/user/exchange/symbol/side

This protects a specific operation or intent.

This is not durable runtime ownership.

It must not be used as proof of ACTIVE runtime authority.

## 3. Durable ownership substrate

The current P3 ownership work added persistent ownership metadata.

Purpose:

- represent runtime owner identity
- represent runtime instance identity
- represent generation
- represent started_at and heartbeat_at
- enable future reconciliation and governance

This is a necessary substrate.

It is not yet a fully governed runtime session.

## 4. Fully governed durable runtime session

A fully governed durable runtime session would require:

- explicit session identity
- durable lifecycle state
- dedicated authority acquisition path
- heartbeat ownership loop
- advisory lock/session reconciliation
- lock loss detection
- fencing semantics
- restart/resume semantics
- stale owner handling
- operator-governed recovery
- fail-closed execution authority

This is not implemented yet.

## Prohibited assumptions

The following assumptions are prohibited:

- runtime_locked means this runtime owns authority
- pg_try_advisory_lock around one tick means durable runtime authority
- semantic intent lock means runtime ownership
- stale heartbeat grants takeover
- frontend request grants runtime authority
- DATA DB state grants runtime authority
- trading_enabled grants execution authority
- ownership projection alone grants broker mutation authority

## runtime_locked semantics

runtime_locked currently reflects scheduler overlap/lock-blocked observation.

It does not prove the current process owns runtime authority.

It must not be used as an ACTIVE authority signal.

## ACTIVE authority boundary

A runtime must not be considered fully ACTIVE unless future implementation proves:

- valid durable ownership row
- current runtime instance identity matches ownership
- advisory lock/session authority is valid
- heartbeat is fresh
- reconciliation is valid
- runtime health is valid
- no LOST_LOCK condition
- no FAILED condition
- no ZOMBIE_SUSPECTED condition

Current projection may report lifecycle states for observability.

That projection is not execution authority.

## Execution authority boundary

Execution authority remains stricter than ownership projection.

Broker mutation requires future enforcement that validates at least:

- trading_enabled is true
- durable ownership is valid and ACTIVE
- advisory lock/session authority is valid
- reconciliation is valid
- runtime health is valid
- no LOST_LOCK / FAILED / ZOMBIE_SUSPECTED condition exists
- gateway path is used

This document does not implement execution authority.

## Known remaining gaps

The following gaps remain explicit and blocking before real control/enforcement:

1. durable runtime session design
2. advisory lock/session lifecycle design
3. ownership-to-lock reconciliation
4. active heartbeat loop governance
5. LOST_LOCK semantics
6. ZOMBIE_SUSPECTED semantics
7. ownership release semantics
8. stale recovery governance
9. operator-visible recovery controls
10. fencing/session epoch enforcement
11. scheduler loop integration
12. execution authority enforcement

## Current safe next steps

Allowed:

- documentation
- projection-only helpers
- read-only runtime status projection
- isolated tests
- audit of historical locking behavior

Not allowed yet:

- treating tick lock as durable authority
- treating semantic intent lock as durable authority
- scheduler_runtime_loop ownership enforcement
- automatic takeover
- stale recovery
- broker mutation authority
- P5 execution authority enforcement
