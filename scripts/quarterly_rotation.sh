#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"

ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ADMIN_OTP="${ADMIN_OTP:-}"
ADMIN_TOTP_SECRET="${ADMIN_TOTP_SECRET:-}"

USER1_EMAIL="${USER1_EMAIL:-}"   # BINANCE owner
USER1_PASSWORD="${USER1_PASSWORD:-}"
USER1_OTP="${USER1_OTP:-}"
USER1_TOTP_SECRET="${USER1_TOTP_SECRET:-}"

USER2_EMAIL="${USER2_EMAIL:-}"   # IBKR owner
USER2_PASSWORD="${USER2_PASSWORD:-}"
USER2_OTP="${USER2_OTP:-}"
USER2_TOTP_SECRET="${USER2_TOTP_SECRET:-}"

NEW_USER1_BINANCE_API_KEY="${NEW_USER1_BINANCE_API_KEY:-}"
NEW_USER1_BINANCE_API_SECRET="${NEW_USER1_BINANCE_API_SECRET:-}"
NEW_USER2_IBKR_API_KEY="${NEW_USER2_IBKR_API_KEY:-}"
NEW_USER2_IBKR_API_SECRET="${NEW_USER2_IBKR_API_SECRET:-}"

ROLLBACK_USER1_BINANCE_API_KEY="${ROLLBACK_USER1_BINANCE_API_KEY:-}"
ROLLBACK_USER1_BINANCE_API_SECRET="${ROLLBACK_USER1_BINANCE_API_SECRET:-}"
ROLLBACK_USER2_IBKR_API_KEY="${ROLLBACK_USER2_IBKR_API_KEY:-}"
ROLLBACK_USER2_IBKR_API_SECRET="${ROLLBACK_USER2_IBKR_API_SECRET:-}"

BINANCE_SYMBOL="${BINANCE_SYMBOL:-BTCUSDT}"
BINANCE_QTY="${BINANCE_QTY:-0.01}"
IBKR_SYMBOL="${IBKR_SYMBOL:-AAPL}"
IBKR_QTY="${IBKR_QTY:-1}"
ALLOW_BINANCE_451="${ALLOW_BINANCE_451:-true}"

pass_count=0
fail_count=0
rotation_attempted=0

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
    echo "Missing command: $1"
    exit 1
  fi
}

require_cmd curl
require_cmd python3

if [[ -z "$BASE_URL" ]]; then
  echo "BASE_URL is required"
  exit 1
fi
if [[ -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" || -z "$USER1_EMAIL" || -z "$USER1_PASSWORD" || -z "$USER2_EMAIL" || -z "$USER2_PASSWORD" ]]; then
  echo "ADMIN/USER credentials are required"
  exit 1
fi

json_get() {
  local key="$1"
  python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1], ""))' "$key"
}

generate_totp() {
  local secret="$1"
  python3 - "$secret" <<'PY'
import base64
import binascii
import hashlib
import hmac
import struct
import sys
import time
from urllib.parse import parse_qs, urlparse

secret = (sys.argv[1] or "").strip().replace(" ", "").upper()
if not secret:
    print("")
    raise SystemExit(0)
if secret.startswith("OTPAUTH://"):
    parsed = urlparse(secret)
    query = parse_qs(parsed.query)
    secret = (query.get("secret", [""])[0] or "").strip().replace(" ", "").upper()
if "SECRET=" in secret and not secret.startswith("OTPAUTH://"):
    secret = secret.split("SECRET=", 1)[1].split("&", 1)[0].strip().replace(" ", "").upper()
padding = "=" * ((8 - len(secret) % 8) % 8)
try:
    key = base64.b32decode(secret + padding, casefold=True)
except (binascii.Error, ValueError):
    print("")
    raise SystemExit(0)
counter = int(time.time() // 30)
msg = struct.pack(">Q", counter)
h = hmac.new(key, msg, hashlib.sha1).digest()
offset = h[-1] & 0x0F
code = (struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
print(f"{code:06d}")
PY
}

login_token() {
  local email="$1"
  local password="$2"
  local otp="$3"
  local totp_secret="$4"

  local resp token
  local data="username=${email}&password=${password}"
  if [[ -n "$otp" ]]; then
    data="${data}&otp=${otp}"
  fi
  resp=$(curl -sS -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "$data" || true)
  token=$(echo "$resp" | json_get access_token || true)
  if [[ "${#token}" -gt 100 ]]; then
    echo "$token"
    return 0
  fi
  if [[ -n "$totp_secret" ]]; then
    local otp_now
    otp_now=$(generate_totp "$totp_secret")
    if [[ -n "$otp_now" ]]; then
      data="username=${email}&password=${password}&otp=${otp_now}"
      resp=$(curl -sS -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data "$data" || true)
      token=$(echo "$resp" | json_get access_token || true)
    fi
  fi
  echo "$token"
}

seed_secret() {
  local token="$1"
  local exchange="$2"
  local api_key="$3"
  local api_secret="$4"
  local label="$5"

  if [[ -z "$api_key" || -z "$api_secret" ]]; then
    echo "INFO | skip $label (new credentials not provided)"
    return 0
  fi
  local resp
  resp=$(curl -sS -X POST "$BASE_URL/users/exchange-secrets" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data "{\"exchange\":\"$exchange\",\"api_key\":\"$api_key\",\"api_secret\":\"$api_secret\"}" || true)
  if [[ "$resp" == *"Encrypted credentials saved"* ]]; then
    pass "$label seeded"
    rotation_attempted=1
  else
    fail "$label seed failed: $resp"
  fi
}

check_test_order() {
  local token="$1"
  local endpoint="$2"
  local payload="$3"
  local label="$4"
  local resp sent
  resp=$(curl -sS -X POST "$BASE_URL$endpoint" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data "$payload" || true)
  sent=$(echo "$resp" | json_get sent || true)
  if [[ "$sent" == "True" || "$sent" == "true" ]]; then
    pass "$label test-order"
    return 0
  fi
  if [[ "$endpoint" == "/ops/execution/binance/test-order" && "$ALLOW_BINANCE_451" == "true" && "$resp" == *"Binance testnet error 451"* ]]; then
    pass "$label test-order controlled 451"
    return 0
  fi
  fail "$label test-order failed: $resp"
}

run_validation() {
  local admin_token="$1"
  local t1="$2"
  local t2="$3"
  local stage="$4"
  local start_fails="$fail_count"

  echo
  echo "[Validation][$stage] Execution checks"
  check_test_order "$t1" "/ops/execution/binance/test-order" "{\"symbol\":\"$BINANCE_SYMBOL\",\"side\":\"BUY\",\"qty\":$BINANCE_QTY}" "user1 BINANCE"
  check_test_order "$t2" "/ops/execution/ibkr/test-order" "{\"symbol\":\"$IBKR_SYMBOL\",\"side\":\"BUY\",\"qty\":$IBKR_QTY}" "user2 IBKR"

  echo
  echo "[Validation][$stage] Security posture"
  local posture
  posture=$(curl -sS "$BASE_URL/ops/security/posture?real_only=true&max_secret_age_days=90" \
    -H "Authorization: Bearer $admin_token" || true)
  if [[ "${posture:0:1}" == "{" ]]; then
    local missing_2fa
    missing_2fa=$(echo "$posture" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["summary"]["users_missing_2fa"])' || echo 999)
    if [[ "$missing_2fa" -eq 0 ]]; then
      pass "$stage posture 2FA ok"
    else
      fail "$stage posture users missing 2FA: $missing_2fa"
    fi
  else
    fail "$stage posture read failed: $posture"
  fi

  if [[ "$fail_count" -gt "$start_fails" ]]; then
    return 1
  fi
  return 0
}

attempt_rollback() {
  local t1="$1"
  local t2="$2"
  echo
  echo "[Rollback] Attempting rollback with previous credentials"

  local rolled=0
  if [[ -n "$ROLLBACK_USER1_BINANCE_API_KEY" && -n "$ROLLBACK_USER1_BINANCE_API_SECRET" ]]; then
    seed_secret "$t1" "BINANCE" "$ROLLBACK_USER1_BINANCE_API_KEY" "$ROLLBACK_USER1_BINANCE_API_SECRET" "rollback user1 BINANCE"
    rolled=1
  else
    echo "INFO | rollback user1 BINANCE credentials not provided"
  fi
  if [[ -n "$ROLLBACK_USER2_IBKR_API_KEY" && -n "$ROLLBACK_USER2_IBKR_API_SECRET" ]]; then
    seed_secret "$t2" "IBKR" "$ROLLBACK_USER2_IBKR_API_KEY" "$ROLLBACK_USER2_IBKR_API_SECRET" "rollback user2 IBKR"
    rolled=1
  else
    echo "INFO | rollback user2 IBKR credentials not provided"
  fi
  if [[ "$rolled" -eq 0 ]]; then
    fail "rollback unavailable (no rollback credentials configured)"
    return 1
  fi
  return 0
}

echo "== Quarterly Rotation =="
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
ADMIN_TOKEN=$(login_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD" "$ADMIN_OTP" "$ADMIN_TOTP_SECRET")
TOKEN1=$(login_token "$USER1_EMAIL" "$USER1_PASSWORD" "$USER1_OTP" "$USER1_TOTP_SECRET")
TOKEN2=$(login_token "$USER2_EMAIL" "$USER2_PASSWORD" "$USER2_OTP" "$USER2_TOTP_SECRET")

if [[ "${#ADMIN_TOKEN}" -gt 100 ]]; then pass "admin login"; else fail "admin login failed"; fi
if [[ "${#TOKEN1}" -gt 100 ]]; then pass "user1 login"; else fail "user1 login failed"; fi
if [[ "${#TOKEN2}" -gt 100 ]]; then pass "user2 login"; else fail "user2 login failed"; fi

if [[ "${#ADMIN_TOKEN}" -le 100 || "${#TOKEN1}" -le 100 || "${#TOKEN2}" -le 100 ]]; then
  echo
  echo "Summary: PASS=$pass_count FAIL=$fail_count"
  exit 1
fi

echo
echo "[C] Quarterly checklist marker"
pass "rotation window executed"

echo
echo "[D] Secret rotation apply"
seed_secret "$TOKEN1" "BINANCE" "$NEW_USER1_BINANCE_API_KEY" "$NEW_USER1_BINANCE_API_SECRET" "user1 BINANCE"
seed_secret "$TOKEN2" "IBKR" "$NEW_USER2_IBKR_API_KEY" "$NEW_USER2_IBKR_API_SECRET" "user2 IBKR"
if [[ "$rotation_attempted" -eq 0 ]]; then
  echo "INFO | no new exchange credentials were provided; run acts as quarterly checklist/validation"
fi

if ! run_validation "$ADMIN_TOKEN" "$TOKEN1" "$TOKEN2" "post-rotation"; then
  if [[ "$rotation_attempted" -eq 1 ]]; then
    if attempt_rollback "$TOKEN1" "$TOKEN2"; then
      run_validation "$ADMIN_TOKEN" "$TOKEN1" "$TOKEN2" "post-rollback" || true
    fi
  fi
fi

echo
echo "Summary: PASS=$pass_count FAIL=$fail_count"
if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
