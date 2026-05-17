# Auto-pick Export State Machine v1

## Purpose

Define safe export lifecycle states for moving Auto-pick DATA rows from AWS DATA DB to local disk DATA DB.

## States

### PENDING
Export batch record created. No copy completed yet.

### EXPORTING
Export process has started.

### EXPORTED
Rows were copied to destination, but checksum/local import verification is not complete.

### VERIFIED
Exported rows were verified against checksum/counts. Only this state can become purge-eligible.

### PURGED
AWS DATA DB rows for the verified export window were purged.

### FAILED
Export failed. Purge is forbidden.

## Allowed transitions

PENDING -> EXPORTING
EXPORTING -> EXPORTED
EXPORTING -> FAILED
EXPORTED -> VERIFIED
EXPORTED -> FAILED
VERIFIED -> PURGED
VERIFIED -> FAILED

## Forbidden transitions

PENDING -> PURGED
EXPORTING -> PURGED
EXPORTED -> PURGED
FAILED -> PURGED
PURGED -> any other state

## Purge rule

Purge is forbidden unless:

- status == VERIFIED
- checksum exists
- snapshot_count and candidate_count are known
- local destination path/URI is recorded
- purged_at is null

## Runtime boundary

Export lifecycle belongs only to DATA plane.

It must never:
- read runtime DB
- mutate runtime DB
- create orders
- create intents
- affect Risk
- affect Execution
