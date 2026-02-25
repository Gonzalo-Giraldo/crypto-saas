#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
EMAIL="${EMAIL:-trader.$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-Trader123!}"
QTY="${QTY:-0.001}"
EXIT_PRICE="${EXIT_PRICE:-50000}"
FEES="${FEES:-0}"

echo "== Health =="
curl -s "$BASE/healthz" && echo
echo

echo "== Register trader (idempotent) =="
REGISTER_RESP=$(curl -s -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  --data "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" || true)
echo "registered/exists: $EMAIL"
echo

echo "== Login =="
LOGIN_RESP=$(curl -s -X POST "$BASE/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=$EMAIL&password=$PASSWORD" \
)
TOKEN=$(echo "$LOGIN_RESP" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(data.get("access_token",""))')
if [[ -z "$TOKEN" ]]; then
  echo "Login failed response:"
  echo "$LOGIN_RESP"
  exit 1
fi
echo "token_ok"
echo

echo "== Create signal =="
SIG=$(
  curl -s -X POST "$BASE/signals" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data-binary @signal1.json \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'
)
echo "signal_id=$SIG"
echo

echo "== Claim =="
curl -s -X POST "$BASE/signals/claim?limit=10" \
  -H "Authorization: Bearer $TOKEN" >/dev/null
echo "claimed"
echo

echo "== Open position from signal =="
OPEN_RESP=$(curl -s -X POST "$BASE/positions/open_from_signal?signal_id=$SIG&qty=$QTY" \
  -H "Authorization: Bearer $TOKEN" || true)
echo "$OPEN_RESP"
echo

if echo "$OPEN_RESP" | grep -q '"detail"'; then
  echo "BLOCKED (expected if risk rules triggered)"
  exit 0
fi

POS=$(echo "$OPEN_RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "position_id=$POS"
echo

echo "== Close position =="
curl -s -X POST "$BASE/positions/close?position_id=$POS&exit_price=$EXIT_PRICE&fees=$FEES" \
  -H "Authorization: Bearer $TOKEN" && echo
echo

echo "== Today risk =="
curl -s "$BASE/positions/risk/today" \
  -H "Authorization: Bearer $TOKEN" && echo
