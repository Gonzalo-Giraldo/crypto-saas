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
- `POST /ops/execution/prepare` (dry-run, worker runtime)
- `POST /ops/execution/binance/test-order` (Binance testnet)
- `POST /ops/execution/ibkr/paper-check` (IBKR connector check)
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
- IBKR connector is currently a paper-check path (credential verification workflow scaffold).

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
- Workflow now stores automatic evidence:
  - Run summary in GitHub Actions
  - Artifact: `smoke_output.log`
  - Automatic issue creation on smoke failure
