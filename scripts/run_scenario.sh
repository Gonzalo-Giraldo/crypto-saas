#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
USER_ID="${1:-}"
QTY="${QTY:-0.001}"
EXIT_PRICE="${EXIT_PRICE:-50000}"
FEES="${FEES:-0}"

if [[ -z "${USER_ID}" ]]; then
  echo "Uso: scripts/run_scenario.sh <USER_ID>"
  exit 1
fi

echo "== Health =="
curl -s "$BASE/healthz" && echo
echo

echo "== Create signal =="
SIG=$(curl -s -X POST "$BASE/signals" \
  -H "Content-Type: application/json" \
  --data-binary @signal1.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "signal_id=$SIG"
echo

echo "== Claim =="
curl -s -X POST "$BASE/signals/claim?user_id=$USER_ID&limit=10" >/dev/null
echo "claimed"
echo

echo "== Open position from signal =="
OPEN_RESP=$(curl -s -X POST "$BASE/positions/open_from_signal?signal_id=$SIG&qty=$QTY" || true)
echo "$OPEN_RESP"
echo

# If blocked, stop
if echo "$OPEN_RESP" | grep -q '"detail"'; then
  echo "BLOCKED (expected if risk rules triggered)"
  exit 0
fi

POS=$(echo "$OPEN_RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "position_id=$POS"
echo

echo "== Close position =="
curl -s -X POST "$BASE/positions/close?position_id=$POS&exit_price=$EXIT_PRICE&fees=$FEES" && echo
echo

echo "== Risk state (sqlite) =="
sqlite3 db.sqlite "select user_id, day, trades_today, realized_pnl_today, daily_stop, max_trades from daily_risk_state where user_id='$USER_ID' order by day desc limit 1;"
echo
