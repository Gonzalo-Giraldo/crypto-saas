# Auto-pick DATA Contract v1

## Purpose

AWS DATA DB stores compact Auto-pick observation data temporarily.

Data is periodically copied to local disk DATA DB for analysis. After verified export, AWS DATA DB content may be purged.

## Tables

### autopick_observation_snapshots

One row per Auto-pick observation snapshot.

Stores:
- snapshot identity
- lineage
- selected candidate summary
- counts
- export/purge markers

### autopick_observation_candidates

Stores the N ranked candidates for each snapshot.

Stores:
- rank
- symbol
- side
- score
- reason
- selected flag
- compact features JSON

### autopick_observation_exports

Tracks AWS DATA DB to local disk DATA DB export batches.

Stores:
- export window
- row counts
- destination
- checksum
- status
- purge confirmation

## Storage rule

AWS DATA DB is temporary operational analytics storage.

Local disk DATA DB is the primary analysis store.

## Forbidden in AWS DATA DB v1

- orders
- fills
- intents
- risk authority
- runtime lifecycle authority
- secrets
- API keys
- raw infinite tick history

## Future

Additional fields/tables may be added only after analysis proves necessity.
