# Auto-pick Export Lifecycle

## Goal

Move temporary AWS DATA DB observations into local disk DATA DB safely and deterministically.

## Lifecycle

AWS DATA DB
→ export batch creation
→ integrity verification
→ local disk import
→ checksum validation
→ export completion mark
→ purge eligibility
→ AWS purge

## Non-negotiables

- Never purge before successful verification.
- Export batches must be append-only.
- Local import must be idempotent.
- Runtime DB is never part of export lifecycle.
- Export failures must block purge.
- Checksums required before purge.
- Purge operations must be explicit and auditable.

## Initial export scope

Tables:
- autopick_observation_snapshots
- autopick_observation_candidates

## Future

Potential future:
- parquet export
- compressed archives
- S3 cold storage
- ML offline datasets
