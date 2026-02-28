# crypto-saas

Backend SaaS (FastAPI + PostgreSQL) for conservative crypto trading operations with:
- authenticated users (JWT),
- signal lifecycle,
- position open/close flow,
- daily risk tracking.

## Stack
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker Compose

## Quick start
1. Bootstrap local environment:
```bash
scripts/bootstrap_dev.sh
```

2. Configure `.env` (created from `.env.example` on bootstrap).

3. Start database:
```bash
docker compose up -d db
```

4. Start API:
```bash
source .venv/bin/activate
uvicorn apps.api.app.main:app --reload
```

5. Run end-to-end scenario:
```bash
scripts/run_scenario.sh
```

## Main endpoints
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/2fa/setup`
- `POST /auth/2fa/verify-enable`
- `POST /auth/2fa/disable`
- `GET /users/me`
- `POST /users/exchange-secrets`
- `GET /users/exchange-secrets`
- `DELETE /users/exchange-secrets/{exchange}`
- `GET /ops/audit/me`
- `GET /ops/audit/all` (admin)
- `GET /ops/risk/daily-compare` (admin, supports `?real_only=true`)
 - `GET /ops/dashboard/summary` (admin, single-screen status summary)
 - `GET /ops/dashboard` (simple web dashboard UI)
- `POST /ops/strategy/assign` (admin)
- `GET /ops/strategy/assignments` (admin)
- `POST /ops/execution/prepare` (dry-run, worker runtime)
- `POST /ops/execution/pretrade/binance/check`
- `POST /ops/execution/pretrade/ibkr/check`
- `POST /ops/execution/exit/binance/check`
- `POST /ops/execution/exit/ibkr/check`
- `POST /ops/execution/binance/test-order` (Binance testnet)
- `POST /ops/execution/ibkr/test-order` (IBKR paper test-order, simulated or bridge)
- `POST /ops/security/reencrypt-exchange-secrets` (admin, key rotation)
- `GET /ops/security/posture` (admin, 2FA + secret age posture)
- `POST /ops/admin/cleanup-smoke-users` (admin, cleanup smoke users with dry-run)
- `POST /signals`
- `GET /signals`
- `POST /signals/claim`
- `POST /positions/open_from_signal`
- `POST /positions/close`
- `GET /positions`
- `GET /positions/risk/today`

## Notes
- Current focus is crypto flow.
- Worker notifications support Telegram via optional env vars.
- If 2FA is enabled for a user, `/auth/login` requires the `otp` form field.
- Optional hardening:
  - `ENFORCE_2FA_FOR_ADMINS=true` forces admins to have 2FA enabled.
  - `ENFORCE_2FA_EMAILS=user1@dominio.com,user2@dominio.com` forces those accounts to have 2FA enabled.
- Exchange credentials are stored encrypted at rest with `ENCRYPTION_KEY`.
- Binance live trading is not enabled here; only testnet `order/test` endpoint is wired.
- IBKR test-order supports:
  - simulated safe mode by default (no money movement),
  - optional bridge mode via `IBKR_BRIDGE_BASE_URL`.
- User risk profile assignment (email-based):
  - `RISK_PROFILE_MODEL2_EMAIL`
  - `RISK_PROFILE_LOOSE_EMAIL`
- Exchange segregation is enforced by strategy assignment:
  - if exchange is disabled for the user, `exchange-secrets` upsert and execution endpoints are blocked.
- `pretrade` now applies strategy-specific entry rules:
  - `SWING_V1` and `INTRADAY_V1`
  - timeframe checks (`trend_tf`, `signal_tf`, `timing_tf`)
  - RR threshold (`rr_estimate`)
  - BINANCE liquidity checks (`volume_24h_usdt`, `spread_bps`, `slippage_bps`)
  - IBKR market/event checks (`in_rth`, `macro_event_block`, `earnings_within_24h`)
- `exit` check now applies strategy-specific exit triggers:
  - stop loss / take profit hit
  - max holding time by strategy
  - trend break / signal reverse
  - IBKR event risk forced exit

## Runbooks
- Local/dev operations: `docs/runbook_operativo.md`
- Staging/production operations: `docs/runbook_produccion.md`
- Daily one-page checklist: `docs/checklist_operativa_1pagina.md`
- NOC-lite decision table: `docs/noc_lite.md`

## Smoke Script
- Automated production smoke checks: `scripts/smoke_prod.sh`
- GitHub Actions workflow: `.github/workflows/smoke-prod.yml`
- Required repository secrets for CI:
  - `SMOKE_BASE_URL` (used on push to `main`)
  - `SMOKE_PASSWORD`
  - `SMOKE_BINANCE_API_KEY`
  - `SMOKE_BINANCE_API_SECRET`
  - `RENDER_DEPLOY_HOOK_URL` (optional, enables auto-remediation redeploy)
- Workflow now stores automatic evidence:
  - Run summary in GitHub Actions
  - Artifacts: `smoke_output.log`, `smoke_remediation.log`
  - Automatic retry policy (`max_attempts=2`) before declaring failure
  - Automatic remediation after final failure (redeploy hook + one extra smoke attempt)
  - Automatic issue creation only after 2 consecutive smoke failures
  - Automatic issue close when smoke recovers
  - Fixed CI smoke user (`SMOKE_EMAIL` optional; defaults to `smoke.ci@example.com`)

## Dual Ops Daily
- Automated two-user daily validation script: `scripts/dual_ops_daily.sh`
- GitHub Actions workflow: `.github/workflows/dual-ops-daily.yml`
- Required repository secrets:
  - `DUAL_USER1_EMAIL` (BINANCE user)
  - `DUAL_USER1_PASSWORD`
  - `DUAL_USER2_EMAIL` (IBKR user)
  - `DUAL_USER2_PASSWORD`
  - `DUAL_ADMIN_EMAIL`
  - `DUAL_ADMIN_PASSWORD`
- Optional repository secrets:
  - `DUAL_USER1_OTP`
  - `DUAL_USER2_OTP`
  - `DUAL_ADMIN_OTP`
  - `DUAL_USER1_TOTP_SECRET` (recommended if 2FA enabled; auto-generates OTP per run)
  - `DUAL_USER2_TOTP_SECRET` (recommended if 2FA enabled; auto-generates OTP per run)
  - `DUAL_ADMIN_TOTP_SECRET` (optional)
  - `DUAL_USER1_BINANCE_API_KEY`
  - `DUAL_USER1_BINANCE_API_SECRET`
  - `DUAL_USER2_IBKR_API_KEY`
  - `DUAL_USER2_IBKR_API_SECRET`
  - `DUAL_USER1_SYMBOL_BINANCE` (default `BTCUSDT`)
  - `DUAL_USER1_QTY_BINANCE` (default `0.01`)
  - `DUAL_USER2_SYMBOL_IBKR` (default `AAPL`)
  - `DUAL_USER2_QTY_IBKR` (default `1`)
  - `DUAL_USER1_EXPECT_EXIT` (default `false`)
  - `DUAL_USER2_EXPECT_EXIT` (default `true`)
- If users have 2FA enabled, prefer `*_TOTP_SECRET` over `*_OTP` to avoid expired OTP failures.
- Reliability and incident policy:
  - Retry policy (`max_attempts=2`)
  - Auto-remediation via `RENDER_DEPLOY_HOOK_URL` if configured
  - Issue escalation only after 2 consecutive failures
  - Auto-close incident on recovery
  - Daily checks include pretrade + test-order + exit-check + segregation assertions + audit validation

## Security Posture Daily
- Daily security posture script: `scripts/security_posture_daily.sh`
- GitHub Actions workflow: `.github/workflows/security-posture-daily.yml`
- Required repository secrets:
  - `DUAL_ADMIN_EMAIL`
  - `DUAL_ADMIN_PASSWORD`
  - `SMOKE_BASE_URL` (or manual `base_url` input)
- Optional repository secrets:
  - `DUAL_ADMIN_OTP`
  - `SECRET_MAX_AGE_DAYS` (default `30`)
- Behavior:
  - Opens issue `[Security Posture Daily] Incident open` when posture fails.
  - Adds comment if incident already exists.
  - Auto-closes incident when posture recovers.

## Cleanup Smoke Users Weekly
- Weekly cleanup workflow: `.github/workflows/cleanup-smoke-users-weekly.yml`
- Script: `scripts/cleanup_smoke_users.sh`
- Endpoint: `POST /ops/admin/cleanup-smoke-users?dry_run=true|false&older_than_days=14`
- Defaults:
  - weekly schedule every Monday
  - `older_than_days=14`
  - scheduled run executes with `dry_run=false`
- Workflow artifact:
  - `cleanup_smoke_users.log`
  - `cleanup_smoke_users_output.json`

## Ops Dashboard
- Browser UI endpoint: `/ops/dashboard`
- Data endpoint: `/ops/dashboard/summary?real_only=true`
- Optional filters:
  - `email_contains=<texto>`
  - `exchange=ALL|BINANCE|IBKR`
  - `real_only=true|false`
  - `include_service_users=true|false` (default `false`; hides `ops.bot.*`)
- Includes a built-in 7-day trend block (`trends_7d`) for:
  - total trades
  - blocked open attempts
  - error events
- Includes profile productivity comparison (`profile_productivity`) by risk profile:
  - users count
  - trades total / utilization
  - blocked opens
  - realized pnl total and average per user
- Usage:
  - login as admin, copy bearer token,
  - open `/ops/dashboard`,
  - paste token and click `Load`,
  - dashboard refreshes every 60 seconds.
  - `Open Incident` button opens a prefilled GitHub issue.

Security posture artifact:
- `Security Posture Daily` now exports `security_dashboard_snapshot.json` as workflow artifact.
- Artifact bundle name format: `security-posture-daily-<run_id>`.
- Preventive rule in `Security Posture Daily`:
  - fails the run if `errors_total` rises for 2 consecutive days (from `trends_7d`) and current day errors reach threshold,
  - marks higher urgency when `pretrade_blocked_last_24h > 0`.
  - threshold env: `PREVENTIVE_MIN_ERRORS` (default `10`).

## Quarterly Rotation
- Quarterly workflow: `.github/workflows/quarterly-rotation.yml`
- Rotation script: `scripts/quarterly_rotation.sh`
- Purpose:
  - open a quarterly checklist issue automatically,
  - apply new exchange credentials automatically when provided,
  - validate post-rotation automatically,
  - attempt rollback automatically if validation fails.
- Required repository secrets:
  - `SMOKE_BASE_URL`
  - `DUAL_ADMIN_EMAIL`
  - `DUAL_ADMIN_PASSWORD`
  - `DUAL_USER1_EMAIL`
  - `DUAL_USER1_PASSWORD`
  - `DUAL_USER2_EMAIL`
  - `DUAL_USER2_PASSWORD`
- Optional auth secrets:
  - `DUAL_ADMIN_TOTP_SECRET`
  - `DUAL_USER1_TOTP_SECRET`
  - `DUAL_USER2_TOTP_SECRET`
- Rotation payload secrets (new credentials):
  - `ROTATE_USER1_BINANCE_API_KEY`
  - `ROTATE_USER1_BINANCE_API_SECRET`
  - `ROTATE_USER2_IBKR_API_KEY`
  - `ROTATE_USER2_IBKR_API_SECRET`
- Rollback payload secrets (previous credentials):
  - `ROLLBACK_USER1_BINANCE_API_KEY`
  - `ROLLBACK_USER1_BINANCE_API_SECRET`
  - `ROLLBACK_USER2_IBKR_API_KEY`
  - `ROLLBACK_USER2_IBKR_API_SECRET`
