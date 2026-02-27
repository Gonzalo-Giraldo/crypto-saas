#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
EMAIL="${EMAIL:-}"
PASSWORD="${PASSWORD:-}"
OTP="${OTP:-}"
SYMBOL_CRYPTO="${SYMBOL_CRYPTO:-BTCUSDT}"
SYMBOL_IBKR="${SYMBOL_IBKR:-AAPL}"
CRYPTO_QTY="${CRYPTO_QTY:-0.01}"
IBKR_QTY="${IBKR_QTY:-1}"
ALLOW_BINANCE_TEST_ERROR="${ALLOW_BINANCE_TEST_ERROR:-true}"
REQUIRE_IBKR_SECRET="${REQUIRE_IBKR_SECRET:-false}"
TOKEN="${TOKEN:-}"

pass_count=0
fail_count=0

pass() {
  echo "PASS | $1"
  pass_count=$((pass_count + 1))
}

fail() {
  echo "FAIL | $1"
  fail_count=$((fail_count + 1))
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

json_has_key() {
  local key="$1"
  python3 -c 'import json,sys; d=json.load(sys.stdin); print("true" if d.get(sys.argv[1]) is not None else "false")' "$key"
}

json_get_key() {
  local key="$1"
  python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1],""))' "$key"
}

array_has_action() {
  local action="$1"
  python3 -c 'import json,sys; arr=json.load(sys.stdin); print("true" if any(x.get("action")==sys.argv[1] for x in arr) else "false")' "$action"
}

require_cmd curl
require_cmd python3

echo "== Smoke Prod =="
echo "BASE_URL=$BASE_URL"

echo
echo "[A] Health"
if HEALTH=$(curl -fsS "$BASE_URL/healthz" 2>/dev/null); then
  STATUS=$(echo "$HEALTH" | json_get_key status)
  if [[ "$STATUS" == "ok" ]]; then
    pass "healthz"
  else
    fail "healthz returned status=$STATUS"
  fi
else
  fail "healthz unreachable"
fi

echo
echo "[B] Auth"
if [[ -z "$TOKEN" ]]; then
  if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
    fail "login skipped: provide TOKEN or EMAIL/PASSWORD"
  else
    LOGIN_DATA="username=$EMAIL&password=$PASSWORD"
    if [[ -n "$OTP" ]]; then
      LOGIN_DATA="$LOGIN_DATA&otp=$OTP"
    fi
    LOGIN_RESP=$(curl -sS -X POST "$BASE_URL/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      --data "$LOGIN_DATA" || true)
    ACCESS_TOKEN=$(echo "$LOGIN_RESP" | json_get_key access_token || true)
    if [[ -n "$ACCESS_TOKEN" ]]; then
      TOKEN="$ACCESS_TOKEN"
      pass "auth login"
    else
      fail "auth login failed: $LOGIN_RESP"
    fi
  fi
else
  pass "auth token provided"
fi

if [[ -z "$TOKEN" ]]; then
  echo
  echo "Summary: PASS=$pass_count FAIL=$fail_count"
  exit 1
fi

AUTH_HEADER="Authorization: Bearer $TOKEN"

echo
echo "[C] Exchange Secrets"
SECRETS_RESP=$(curl -sS "$BASE_URL/users/exchange-secrets" -H "$AUTH_HEADER" || true)
if [[ "${SECRETS_RESP:0:1}" == "[" ]]; then
  pass "list exchange secrets"
  HAS_BINANCE=$(echo "$SECRETS_RESP" | python3 -c 'import json,sys; arr=json.load(sys.stdin); print("true" if any(x.get("exchange")=="BINANCE" for x in arr) else "false")')
  HAS_IBKR=$(echo "$SECRETS_RESP" | python3 -c 'import json,sys; arr=json.load(sys.stdin); print("true" if any(x.get("exchange")=="IBKR" for x in arr) else "false")')
  if [[ "$HAS_BINANCE" == "true" ]]; then
    pass "BINANCE secret configured"
  else
    fail "BINANCE secret missing"
  fi
  if [[ "$REQUIRE_IBKR_SECRET" == "true" ]]; then
    if [[ "$HAS_IBKR" == "true" ]]; then
      pass "IBKR secret configured"
    else
      fail "IBKR secret missing"
    fi
  fi
else
  fail "list exchange secrets failed: $SECRETS_RESP"
fi

echo
echo "[D] Execution"
PREP_RESP=$(curl -sS -X POST "$BASE_URL/ops/execution/prepare" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  --data "{\"exchange\":\"BINANCE\",\"symbol\":\"$SYMBOL_CRYPTO\",\"side\":\"BUY\",\"qty\":$CRYPTO_QTY}" || true)
PREP_MODE=$(echo "$PREP_RESP" | json_get_key mode || true)
if [[ "$PREP_MODE" == "dry_run" ]]; then
  pass "execution prepare dry_run"
else
  fail "execution prepare failed: $PREP_RESP"
fi

BINANCE_RESP=$(curl -sS -X POST "$BASE_URL/ops/execution/binance/test-order" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  --data "{\"symbol\":\"$SYMBOL_CRYPTO\",\"side\":\"BUY\",\"qty\":$CRYPTO_QTY}" || true)
BINANCE_SENT=$(echo "$BINANCE_RESP" | json_get_key sent || true)
if [[ "$BINANCE_SENT" == "True" || "$BINANCE_SENT" == "true" ]]; then
  pass "binance test-order"
else
  if [[ "$ALLOW_BINANCE_TEST_ERROR" == "true" ]] && [[ "$BINANCE_RESP" == *"Binance test order failed"* ]]; then
    pass "binance test-order reachable (error controlled)"
  else
    fail "binance test-order failed: $BINANCE_RESP"
  fi
fi

IBKR_RESP=$(curl -sS -X POST "$BASE_URL/ops/execution/ibkr/test-order" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  --data "{\"symbol\":\"$SYMBOL_IBKR\",\"side\":\"BUY\",\"qty\":$IBKR_QTY}" || true)
IBKR_EXPECT_AUDIT="true"
IBKR_SENT=$(echo "$IBKR_RESP" | json_get_key sent || true)
if [[ "$IBKR_SENT" == "True" || "$IBKR_SENT" == "true" ]]; then
  pass "ibkr test-order"
else
  if [[ "$REQUIRE_IBKR_SECRET" == "true" ]]; then
    fail "ibkr test-order failed: $IBKR_RESP"
  else
    IBKR_EXPECT_AUDIT="false"
    pass "ibkr test-order optional (not enforced): $IBKR_RESP"
  fi
fi

echo
echo "[E] Audit"
AUDIT_RESP=$(curl -sS "$BASE_URL/ops/audit/me?limit=100" -H "$AUTH_HEADER" || true)
if [[ "${AUDIT_RESP:0:1}" == "[" ]]; then
  pass "audit list"
  HAS_LOGIN=$(echo "$AUDIT_RESP" | array_has_action "auth.login.success")
  HAS_PREP=$(echo "$AUDIT_RESP" | array_has_action "execution.prepare")
  HAS_IBKR_OK=$(echo "$AUDIT_RESP" | array_has_action "execution.ibkr.test_order.success")
  HAS_IBKR_ERR=$(echo "$AUDIT_RESP" | array_has_action "execution.ibkr.test_order.error")
  HAS_BINANCE_OK=$(echo "$AUDIT_RESP" | array_has_action "execution.binance.test_order.success")
  HAS_BINANCE_ERR=$(echo "$AUDIT_RESP" | array_has_action "execution.binance.test_order.error")

  [[ "$HAS_LOGIN" == "true" ]] && pass "audit auth.login.success" || fail "audit missing auth.login.success"
  [[ "$HAS_PREP" == "true" ]] && pass "audit execution.prepare" || fail "audit missing execution.prepare"
  if [[ "$IBKR_EXPECT_AUDIT" == "true" ]]; then
    if [[ "$HAS_IBKR_OK" == "true" || "$HAS_IBKR_ERR" == "true" ]]; then
      pass "audit ibkr test-order event"
    else
      fail "audit missing ibkr test-order event"
    fi
  else
    pass "audit ibkr event optional (not enforced)"
  fi
  if [[ "$HAS_BINANCE_OK" == "true" || "$HAS_BINANCE_ERR" == "true" ]]; then
    pass "audit binance test-order event"
  else
    fail "audit missing binance test-order event"
  fi
else
  fail "audit list failed: $AUDIT_RESP"
fi

echo
echo "Summary: PASS=$pass_count FAIL=$fail_count"
if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
