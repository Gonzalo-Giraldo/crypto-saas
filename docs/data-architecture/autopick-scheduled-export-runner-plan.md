# Auto-pick Scheduled Export Runner Plan

## Objective

Introduce a controlled DATA-only scheduled runner for Auto-pick observation exports.

The runner must produce deterministic export batches and route them through the existing storage adapter contract:

```text
DATA DB rows
→ deterministic JSONL
→ checksum
→ manifest
→ disk/s3 storage adapter
→ remote verification
→ lifecycle persistence
