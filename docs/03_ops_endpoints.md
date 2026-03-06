# OPS Endpoints (Learning Pipeline)

## Label outcomes
- `POST /ops/admin/learning/label?dry_run=true&horizon_minutes=60&limit=500`
- Labels pending/no_price outcomes when due time is reached.

## Retention cleanup
- `POST /ops/admin/learning/retention/run?dry_run=true&raw_ttl_days=180&rollup_ttl_days=730`
- Deletes old raw snapshots/outcomes and old rollups.

## Refresh rollups
- `POST /ops/admin/learning/rollup/refresh?hours=48&dry_run=false`
- Rebuilds hourly aggregates from labeled outcomes.

## Status
- `GET /ops/admin/learning/status`
- Returns counts for `pending`, `labeled`, `expired`, `no_price`, plus total snapshots/outcomes.

## Dataset
- `GET /ops/admin/learning/dataset?hours=24&limit=1000&outcome_status=ALL&exchange=ALL`
- Returns training-ready rows (features + outcome labels).

## Rollup report
- `GET /ops/admin/learning/rollup?hours=72&limit=2000&exchange=ALL`
- Returns hourly performance aggregates.
