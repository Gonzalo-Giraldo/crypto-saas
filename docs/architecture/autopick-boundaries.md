# Auto-pick Boundaries

Auto-pick must evolve as a deterministic, auditable, observation-first module before AWS migration.

## Planes

### Runtime Authority Plane

Owns runtime decisions and operational truth.

Allowed:
- Convert a validated observation report into `AutoPickDecision` or `AutoPickNoTrade`.
- Feed Risk/Intent only through explicit runtime contracts.

Forbidden:
- Persist analytics snapshots.
- Own historical replay data.
- Mutate scoring math during infrastructure work.

### Observation Plane

Owns read-only Auto-pick projections.

Allowed:
- Produce `AutoPickObservationReport`.
- Produce selected candidate, ranked candidates, rejection evidence and timing.
- Remain broker-mutation free.

Forbidden:
- Create Risk.
- Create Intent.
- Execute broker mutations.
- Write runtime authority state.

### Data Plane

Owns append-only observation evidence and replay lineage.

Allowed:
- Persist compact observation metadata.
- Persist hashes, lineage, selected projection and rejection evidence.
- Support offline replay/analytics.

Forbidden:
- Store runtime authority truth.
- Store orders, fills, intents, risk decisions or lifecycle authority.
- Mutate production/runtime DB.

### AWS Data Plane

Future deployment target for autonomous collection, snapshot storage, deterministic evaluation and observability.

Allowed:
- Run Auto-pick observation independently.
- Store compact metadata in data DB.
- Store raw replay payloads in object storage when enabled.

Forbidden:
- Become execution authority before explicit runtime migration approval.

## Current Risk

There are currently two Auto-pick evaluation paths:

1. Direct runtime observation path.
2. Snapshot deterministic observation path.

This creates future risk of silent divergence.

## Target Architecture

Market collector
-> immutable snapshot
-> deterministic evaluation engine
-> observation report
-> runtime decision adapter
-> Risk/Intent

There must be one factual evaluation engine shared by runtime and replay paths.

## Non-negotiables

- No scoring math changes during architecture extraction.
- No selection semantics changes.
- No Risk/Intent/Execution coupling in observation/data plane.
- No runtime DB schema mutation for data analytics.
- Data schema changes must use `alembic_data`.
- Runtime schema changes must use runtime `alembic`.
