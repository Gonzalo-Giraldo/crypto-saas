#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"

USER1_EMAIL="${USER1_EMAIL:-}"     # BINANCE user
USER1_PASSWORD="${USER1_PASSWORD:-}"
USER1_OTP="${USER1_OTP:-}"
USER1_SYMBOL_BINANCE="${USER1_SYMBOL_BINANCE:-BTCUSDT}"
USER1_QTY_BINANCE="${USER1_QTY_BINANCE:-0.01}"
USER1_BINANCE_API_KEY="${USER1_BINANCE_API_KEY:-}"
USER1_BINANCE_API_SECRET="${USER1_BINANCE_API_SECRET:-}"

USER2_EMAIL="${USER2_EMAIL:-}"     # IBKR user
USER2_PASSWORD="${USER2_PASSWORD:-}"
USER2_OTP="${USER2_OTP:-}"
USER2_SYMBOL_IBKR="${USER2_SYMBOL_IBKR:-AAPL}"
USER2_QTY_IBKR="${USER2_QTY_IBKR:-1}"
USER2_IBKR_API_KEY="${USER2_IBKR_API_KEY:-}"
USER2_IBKR_API_SECRET="${USER2_IBKR_API_SECRET:-}"

ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ADMIN_OTP="${ADMIN_OTP:-}"

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

require_cmd curl
require_cmd python3

if [[ -z "${BASE_URL}" ]]; then
  echo "BASE_URL is required"
  exit 1
fi
if [[ -z "${USER1_EMAIL}" || -z "${USER1_PASSWORD}" || -z "${USER2_EMAIL}" || -z "${USER2_PASSWORD}" ]]; then
  echo "USER1/USER2 credentials are required"
  exit 1
fi
if [[ -z "${ADMIN_EMAIL}" || -z "${ADMIN_PASSWORD}" ]]; then
  echo "ADMIN credentials are required"
  exit 1
fi

json_get() {
  local key="$1"
  python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1], ""))' "$key"
}

login_token() {
  local email="$1"
  local password="$2"
  local otp="${3:-}"
  local data="username=${email}&password=${password}"
  if [[ -n "${otp}" ]]; then
    data="${data}&otp=${otp}"
  fi
  local resp
  resp=$(curl -sS -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "$data" || true)
  local token
  token=$(echo "$resp" | json_get access_token || true)
  echo "$token"
}

seed_exchange_secret_if_present() {
  local token="$1"
  local exchange="$2"
  local api_key="$3"
  local api_secret="$4"
  local label="$5"

  if [[ -z "$api_key" || -z "$api_secret" ]]; then
    echo "INFO | skip secret seed ($label): credentials not provided"
    return 0
  fi

  local resp
  resp=$(curl -sS -X POST "$BASE_URL/users/exchange-secrets" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data "{\"exchange\":\"$exchange\",\"api_key\":\"$api_key\",\"api_secret\":\"$api_secret\"}" || true)
  if [[ "$resp" == *"Encrypted credentials saved"* ]]; then
    pass "seed $label secret"
  else
    fail "seed $label secret failed: $resp"
  fi
}

check_pretrade() {
  local token="$1"
  local endpoint="$2"
  local payload="$3"
  local label="$4"
  local resp
  resp=$(curl -sS -X POST "$BASE_URL$endpoint" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data "$payload" || true)
  local passed
  passed=$(echo "$resp" | json_get passed || true)
  if [[ "$passed" == "True" || "$passed" == "true" ]]; then
    pass "$label pretrade"
  else
    fail "$label pretrade failed: $resp"
  fi
}

check_test_order() {
  local token="$1"
  local endpoint="$2"
  local payload="$3"
  local label="$4"
  local resp
  resp=$(curl -sS -X POST "$BASE_URL$endpoint" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data "$payload" || true)
  local sent
  sent=$(echo "$resp" | json_get sent || true)
  if [[ "$sent" == "True" || "$sent" == "true" ]]; then
    pass "$label test-order"
  else
    fail "$label test-order failed: $resp"
  fi
}

check_expected_403() {
  local token="$1"
  local endpoint="$2"
  local payload="$3"
  local expected_msg="$4"
  local label="$5"
  local status
  status=$(curl -sS -o /tmp/dual_ops_resp.json -w "%{http_code}" -X POST "$BASE_URL$endpoint" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data "$payload" || true)
  local body
  body=$(cat /tmp/dual_ops_resp.json 2>/dev/null || true)
  if [[ "$status" == "403" && "$body" == *"$expected_msg"* ]]; then
    pass "$label blocked as expected"
  else
    fail "$label expected 403 failed: status=$status body=$body"
  fi
}

echo "== Dual Ops Daily =="
echo "BASE_URL=$BASE_URL"
echo "USER1_EMAIL=$USER1_EMAIL"
echo "USER2_EMAIL=$USER2_EMAIL"

echo
echo "[A] Health"
if health=$(curl -fsS "$BASE_URL/healthz" 2>/dev/null); then
  status=$(echo "$health" | json_get status)
  if [[ "$status" == "ok" ]]; then
    pass "healthz"
  else
    fail "healthz status=$status"
  fi
else
  fail "healthz unreachable"
fi

echo
echo "[B] Login"
TOKEN1=$(login_token "$USER1_EMAIL" "$USER1_PASSWORD" "$USER1_OTP")
TOKEN2=$(login_token "$USER2_EMAIL" "$USER2_PASSWORD" "$USER2_OTP")
ADMIN_TOKEN=$(login_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD" "$ADMIN_OTP")

if [[ "${#TOKEN1}" -gt 100 ]]; then pass "user1 login"; else fail "user1 login failed"; fi
if [[ "${#TOKEN2}" -gt 100 ]]; then pass "user2 login"; else fail "user2 login failed"; fi
if [[ "${#ADMIN_TOKEN}" -gt 100 ]]; then pass "admin login"; else fail "admin login failed"; fi

if [[ "${#TOKEN1}" -le 100 || "${#TOKEN2}" -le 100 || "${#ADMIN_TOKEN}" -le 100 ]]; then
  echo
  echo "Summary: PASS=$pass_count FAIL=$fail_count"
  exit 1
fi

echo
echo "[C] Optional Secret Seed"
seed_exchange_secret_if_present "$TOKEN1" "BINANCE" "$USER1_BINANCE_API_KEY" "$USER1_BINANCE_API_SECRET" "user1 BINANCE"
seed_exchange_secret_if_present "$TOKEN2" "IBKR" "$USER2_IBKR_API_KEY" "$USER2_IBKR_API_SECRET" "user2 IBKR"

echo
echo "[D] Pretrade and Test Orders"
check_pretrade "$TOKEN1" "/ops/execution/pretrade/binance/check" "{\"symbol\":\"$USER1_SYMBOL_BINANCE\",\"side\":\"BUY\",\"qty\":$USER1_QTY_BINANCE}" "user1 BINANCE"
check_pretrade "$TOKEN2" "/ops/execution/pretrade/ibkr/check" "{\"symbol\":\"$USER2_SYMBOL_IBKR\",\"side\":\"BUY\",\"qty\":$USER2_QTY_IBKR}" "user2 IBKR"

check_test_order "$TOKEN1" "/ops/execution/binance/test-order" "{\"symbol\":\"$USER1_SYMBOL_BINANCE\",\"side\":\"BUY\",\"qty\":$USER1_QTY_BINANCE}" "user1 BINANCE"
check_test_order "$TOKEN2" "/ops/execution/ibkr/test-order" "{\"symbol\":\"$USER2_SYMBOL_IBKR\",\"side\":\"BUY\",\"qty\":$USER2_QTY_IBKR}" "user2 IBKR"

echo
echo "[E] Segregation Assertions"
check_expected_403 "$TOKEN1" "/ops/execution/ibkr/test-order" "{\"symbol\":\"$USER2_SYMBOL_IBKR\",\"side\":\"BUY\",\"qty\":$USER2_QTY_IBKR}" "Exchange IBKR is disabled for this user" "user1 IBKR"
check_expected_403 "$TOKEN2" "/ops/execution/binance/test-order" "{\"symbol\":\"$USER1_SYMBOL_BINANCE\",\"side\":\"BUY\",\"qty\":$USER1_QTY_BINANCE}" "Exchange BINANCE is disabled for this user" "user2 BINANCE"

echo
echo "[F] Daily Compare"
compare=$(curl -sS "$BASE_URL/ops/risk/daily-compare?real_only=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN" || true)
if [[ "${compare:0:1}" == "{" ]]; then
  users_count=$(echo "$compare" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("users",[])))' || echo 0)
  if [[ "$users_count" -ge 2 ]]; then
    pass "daily compare real_only users=$users_count"
  else
    fail "daily compare expected >=2 users, got $users_count"
  fi
else
  fail "daily compare failed: $compare"
fi

echo
echo "Summary: PASS=$pass_count FAIL=$fail_count"
if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
