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
- `POST /ops/execution/prepare` (dry-run, worker runtime)
- `POST /ops/execution/binance/test-order` (Binance testnet)
- `POST /ops/execution/ibkr/test-order` (IBKR paper test-order, simulated or bridge)
- `POST /ops/security/reencrypt-exchange-secrets` (admin, key rotation)
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
- Exchange credentials are stored encrypted at rest with `ENCRYPTION_KEY`.
- Binance live trading is not enabled here; only testnet `order/test` endpoint is wired.
- IBKR test-order supports:
  - simulated safe mode by default (no money movement),
  - optional bridge mode via `IBKR_BRIDGE_BASE_URL`.
- User risk profile assignment (email-based):
  - `RISK_PROFILE_MODEL2_EMAIL`
  - `RISK_PROFILE_LOOSE_EMAIL`

## Runbooks
- Local/dev operations: `docs/runbook_operativo.md`
- Staging/production operations: `docs/runbook_produccion.md`
- Daily one-page checklist: `docs/checklist_operativa_1pagina.md`

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
