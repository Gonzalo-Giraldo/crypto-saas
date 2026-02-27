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
USER1_EXIT_ENTRY_PRICE="${USER1_EXIT_ENTRY_PRICE:-50000}"
USER1_EXIT_CURRENT_PRICE="${USER1_EXIT_CURRENT_PRICE:-50750}"
USER1_EXIT_STOP_LOSS="${USER1_EXIT_STOP_LOSS:-49500}"
USER1_EXIT_TAKE_PROFIT="${USER1_EXIT_TAKE_PROFIT:-51000}"
USER1_EXIT_OPENED_MINUTES="${USER1_EXIT_OPENED_MINUTES:-180}"
USER1_EXIT_TREND_BREAK="${USER1_EXIT_TREND_BREAK:-false}"
USER1_EXIT_SIGNAL_REVERSE="${USER1_EXIT_SIGNAL_REVERSE:-false}"
USER1_EXPECT_EXIT="${USER1_EXPECT_EXIT:-false}"

USER2_EMAIL="${USER2_EMAIL:-}"     # IBKR user
USER2_PASSWORD="${USER2_PASSWORD:-}"
USER2_OTP="${USER2_OTP:-}"
USER2_SYMBOL_IBKR="${USER2_SYMBOL_IBKR:-AAPL}"
USER2_QTY_IBKR="${USER2_QTY_IBKR:-1}"
USER2_IBKR_API_KEY="${USER2_IBKR_API_KEY:-}"
USER2_IBKR_API_SECRET="${USER2_IBKR_API_SECRET:-}"
USER2_EXIT_ENTRY_PRICE="${USER2_EXIT_ENTRY_PRICE:-180}"
USER2_EXIT_CURRENT_PRICE="${USER2_EXIT_CURRENT_PRICE:-179}"
USER2_EXIT_STOP_LOSS="${USER2_EXIT_STOP_LOSS:-178}"
USER2_EXIT_TAKE_PROFIT="${USER2_EXIT_TAKE_PROFIT:-183}"
USER2_EXIT_OPENED_MINUTES="${USER2_EXIT_OPENED_MINUTES:-500}"
USER2_EXIT_TREND_BREAK="${USER2_EXIT_TREND_BREAK:-false}"
USER2_EXIT_SIGNAL_REVERSE="${USER2_EXIT_SIGNAL_REVERSE:-false}"
USER2_EXIT_MACRO_EVENT_BLOCK="${USER2_EXIT_MACRO_EVENT_BLOCK:-true}"
USER2_EXIT_EARNINGS_WITHIN_24H="${USER2_EXIT_EARNINGS_WITHIN_24H:-false}"
USER2_EXPECT_EXIT="${USER2_EXPECT_EXIT:-true}"

ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ADMIN_OTP="${ADMIN_OTP:-}"
BINANCE_GEO_RESTRICT_AS_PASS="${BINANCE_GEO_RESTRICT_AS_PASS:-true}"

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

array_has_action() {
  local action="$1"
  python3 -c 'import json,sys; arr=json.load(sys.stdin); print("true" if any(x.get("action")==sys.argv[1] for x in arr) else "false")' "$action"
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

check_exit_decision() {
  local token="$1"
  local endpoint="$2"
  local payload="$3"
  local expected="$4"
  local label="$5"
  local resp
  resp=$(curl -sS -X POST "$BASE_URL$endpoint" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data "$payload" || true)
  local should_exit
  should_exit=$(echo "$resp" | json_get should_exit || true)
  if [[ "$should_exit" == "True" ]]; then should_exit="true"; fi
  if [[ "$should_exit" == "False" ]]; then should_exit="false"; fi
  expected=$(echo "$expected" | tr '[:upper:]' '[:lower:]')
  if [[ "$should_exit" == "$expected" ]]; then
    pass "$label exit-check expected=$expected"
  else
    fail "$label exit-check mismatch expected=$expected got=$should_exit resp=$resp"
  fi
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
  elif [[ "$endpoint" == "/ops/execution/binance/test-order" && "$BINANCE_GEO_RESTRICT_AS_PASS" == "true" && "$resp" == *"restricted location"* ]]; then
    pass "$label test-order reachable (binance geo-restricted controlled)"
  elif [[ "$endpoint" == "/ops/execution/binance/test-order" && "$BINANCE_GEO_RESTRICT_AS_PASS" == "true" && "$resp" == *"Binance testnet error 451"* ]]; then
    pass "$label test-order reachable (binance 451 controlled)"
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
echo "[E] Exit Checks"
check_exit_decision "$TOKEN1" "/ops/execution/exit/binance/check" \
  "{\"symbol\":\"$USER1_SYMBOL_BINANCE\",\"side\":\"BUY\",\"entry_price\":$USER1_EXIT_ENTRY_PRICE,\"current_price\":$USER1_EXIT_CURRENT_PRICE,\"stop_loss\":$USER1_EXIT_STOP_LOSS,\"take_profit\":$USER1_EXIT_TAKE_PROFIT,\"opened_minutes\":$USER1_EXIT_OPENED_MINUTES,\"trend_break\":$USER1_EXIT_TREND_BREAK,\"signal_reverse\":$USER1_EXIT_SIGNAL_REVERSE}" \
  "$USER1_EXPECT_EXIT" "user1 BINANCE"
check_exit_decision "$TOKEN2" "/ops/execution/exit/ibkr/check" \
  "{\"symbol\":\"$USER2_SYMBOL_IBKR\",\"side\":\"BUY\",\"entry_price\":$USER2_EXIT_ENTRY_PRICE,\"current_price\":$USER2_EXIT_CURRENT_PRICE,\"stop_loss\":$USER2_EXIT_STOP_LOSS,\"take_profit\":$USER2_EXIT_TAKE_PROFIT,\"opened_minutes\":$USER2_EXIT_OPENED_MINUTES,\"trend_break\":$USER2_EXIT_TREND_BREAK,\"signal_reverse\":$USER2_EXIT_SIGNAL_REVERSE,\"macro_event_block\":$USER2_EXIT_MACRO_EVENT_BLOCK,\"earnings_within_24h\":$USER2_EXIT_EARNINGS_WITHIN_24H}" \
  "$USER2_EXPECT_EXIT" "user2 IBKR"

echo
echo "[F] Segregation Assertions"
check_expected_403 "$TOKEN1" "/ops/execution/ibkr/test-order" "{\"symbol\":\"$USER2_SYMBOL_IBKR\",\"side\":\"BUY\",\"qty\":$USER2_QTY_IBKR}" "Exchange IBKR is disabled for this user" "user1 IBKR"
check_expected_403 "$TOKEN2" "/ops/execution/binance/test-order" "{\"symbol\":\"$USER1_SYMBOL_BINANCE\",\"side\":\"BUY\",\"qty\":$USER1_QTY_BINANCE}" "Exchange BINANCE is disabled for this user" "user2 BINANCE"

echo
echo "[G] Audit Checks"
AUDIT1=$(curl -sS "$BASE_URL/ops/audit/me?limit=120" -H "Authorization: Bearer $TOKEN1" || true)
AUDIT2=$(curl -sS "$BASE_URL/ops/audit/me?limit=120" -H "Authorization: Bearer $TOKEN2" || true)
if [[ "${AUDIT1:0:1}" == "[" ]]; then
  HAS_EXIT1_HOLD=$(echo "$AUDIT1" | array_has_action "exit.check.hold")
  HAS_EXIT1_TRG=$(echo "$AUDIT1" | array_has_action "exit.check.triggered")
  if [[ "$HAS_EXIT1_HOLD" == "true" || "$HAS_EXIT1_TRG" == "true" ]]; then
    pass "audit user1 exit.check.*"
  else
    fail "audit user1 missing exit.check.*"
  fi
else
  fail "audit user1 list failed: $AUDIT1"
fi
if [[ "${AUDIT2:0:1}" == "[" ]]; then
  HAS_EXIT2_HOLD=$(echo "$AUDIT2" | array_has_action "exit.check.hold")
  HAS_EXIT2_TRG=$(echo "$AUDIT2" | array_has_action "exit.check.triggered")
  if [[ "$HAS_EXIT2_HOLD" == "true" || "$HAS_EXIT2_TRG" == "true" ]]; then
    pass "audit user2 exit.check.*"
  else
    fail "audit user2 missing exit.check.*"
  fi
else
  fail "audit user2 list failed: $AUDIT2"
fi

echo
echo "[H] Daily Compare"
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
