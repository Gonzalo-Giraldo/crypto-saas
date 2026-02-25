#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo
echo "Bootstrap complete."
echo "Next steps:"
echo "1) Start DB: docker compose up -d db"
echo "2) Start API: uvicorn apps.api.app.main:app --reload"
echo "3) Run scenario: scripts/run_scenario.sh"
