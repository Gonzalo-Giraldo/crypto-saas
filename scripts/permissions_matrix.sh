#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ADMIN_OTP="${ADMIN_OTP:-}"
ADMIN_TOTP_SECRET="${ADMIN_TOTP_SECRET:-}"
USER1_EMAIL="${USER1_EMAIL:-}"
USER1_PASSWORD="${USER1_PASSWORD:-}"
USER1_OTP="${USER1_OTP:-}"
USER1_TOTP_SECRET="${USER1_TOTP_SECRET:-}"
USER2_EMAIL="${USER2_EMAIL:-}"
USER2_PASSWORD="${USER2_PASSWORD:-}"
USER2_OTP="${USER2_OTP:-}"
USER2_TOTP_SECRET="${USER2_TOTP_SECRET:-}"
DISABLED_EMAIL="${DISABLED_EMAIL:-}"
DISABLED_PASSWORD="${DISABLED_PASSWORD:-}"

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

if [[ -z "$BASE_URL" || -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" || -z "$USER1_EMAIL" || -z "$USER1_PASSWORD" ]]; then
  echo "Missing required envs: BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, USER1_EMAIL, USER1_PASSWORD"
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
    maybe = secret.split("SECRET=", 1)[1].split("&", 1)[0]
    secret = maybe.strip().replace(" ", "").upper()

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
  local otp="${3:-}"
  local data="username=${email}&password=${password}"
  if [[ -n "$otp" ]]; then
    data="${data}&otp=${otp}"
  fi
  curl -sS -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "$data" || true
}

expect_status() {
  local token="$1"
  local method="$2"
  local path="$3"
  local expected_status="$4"
  local label="$5"
  local data="${6:-}"
  local tmp_body="/tmp/perm_matrix_body.json"
  local status
  if [[ -n "$data" ]]; then
    status=$(curl -sS -o "$tmp_body" -w "%{http_code}" -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $token" \
      -H "Content-Type: application/json" \
      --data "$data" || true)
  else
    status=$(curl -sS -o "$tmp_body" -w "%{http_code}" -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $token" || true)
  fi

  if [[ "$status" == "$expected_status" ]]; then
    pass "$label status=$status"
  else
    local body
    body=$(cat "$tmp_body" 2>/dev/null || true)
    fail "$label expected=$expected_status got=$status body=$body"
  fi
}

echo "== Permissions Matrix =="
echo "BASE_URL=$BASE_URL"
echo "USER1_EMAIL=$USER1_EMAIL"
if [[ -n "$USER2_EMAIL" ]]; then
  echo "USER2_EMAIL=$USER2_EMAIL"
fi

echo
echo "[A] Health"
if health=$(curl -fsS "$BASE_URL/healthz" 2>/dev/null); then
  status=$(echo "$health" | json_get status || true)
  if [[ "$status" == "ok" ]]; then
    pass "healthz"
  else
    fail "healthz status=$status"
  fi
else
  fail "healthz unreachable"
fi

echo
echo "[B] Login by role"
ADMIN_RESP=$(login_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD" "$ADMIN_OTP")
ADMIN_TOKEN=$(echo "$ADMIN_RESP" | json_get access_token || true)
if [[ "${#ADMIN_TOKEN}" -le 100 && -n "$ADMIN_TOTP_SECRET" ]]; then
  ADMIN_OTP=$(generate_totp "$ADMIN_TOTP_SECRET")
  if [[ -n "$ADMIN_OTP" ]]; then
    ADMIN_RESP=$(login_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD" "$ADMIN_OTP")
    ADMIN_TOKEN=$(echo "$ADMIN_RESP" | json_get access_token || true)
  fi
fi
if [[ "${#ADMIN_TOKEN}" -gt 100 ]]; then
  pass "admin login"
else
  fail "admin login failed: $ADMIN_RESP"
fi

USER1_RESP=$(login_token "$USER1_EMAIL" "$USER1_PASSWORD" "$USER1_OTP")
USER1_TOKEN=$(echo "$USER1_RESP" | json_get access_token || true)
if [[ "${#USER1_TOKEN}" -le 100 && -n "$USER1_TOTP_SECRET" ]]; then
  USER1_OTP=$(generate_totp "$USER1_TOTP_SECRET")
  if [[ -n "$USER1_OTP" ]]; then
    USER1_RESP=$(login_token "$USER1_EMAIL" "$USER1_PASSWORD" "$USER1_OTP")
    USER1_TOKEN=$(echo "$USER1_RESP" | json_get access_token || true)
  fi
fi
if [[ "${#USER1_TOKEN}" -gt 100 ]]; then
  pass "user1 login (trader)"
else
  fail "user1 login failed: $USER1_RESP"
fi

USER2_TOKEN=""
if [[ -n "$USER2_EMAIL" && -n "$USER2_PASSWORD" ]]; then
  USER2_RESP=$(login_token "$USER2_EMAIL" "$USER2_PASSWORD" "$USER2_OTP")
  USER2_TOKEN=$(echo "$USER2_RESP" | json_get access_token || true)
  if [[ "${#USER2_TOKEN}" -le 100 && -n "$USER2_TOTP_SECRET" ]]; then
    USER2_OTP=$(generate_totp "$USER2_TOTP_SECRET")
    if [[ -n "$USER2_OTP" ]]; then
      USER2_RESP=$(login_token "$USER2_EMAIL" "$USER2_PASSWORD" "$USER2_OTP")
      USER2_TOKEN=$(echo "$USER2_RESP" | json_get access_token || true)
    fi
  fi
  if [[ "${#USER2_TOKEN}" -gt 100 ]]; then
    pass "user2 login (trader)"
  else
    fail "user2 login failed: $USER2_RESP"
  fi
else
  echo "INFO | user2 creds not provided, skipping user2 checks"
fi

if [[ "${#ADMIN_TOKEN}" -le 100 || "${#USER1_TOKEN}" -le 100 ]]; then
  echo
  echo "Summary: PASS=$pass_count FAIL=$fail_count"
  exit 1
fi

echo
echo "[C] Admin vs trader authorization"
expect_status "$ADMIN_TOKEN" "GET" "/users" "200" "admin can list users"
expect_status "$USER1_TOKEN" "GET" "/users" "403" "trader blocked list users"
expect_status "$ADMIN_TOKEN" "GET" "/ops/audit/all?limit=1" "200" "admin can read full audit"
expect_status "$USER1_TOKEN" "GET" "/ops/audit/all?limit=1" "403" "trader blocked full audit"
expect_status "$ADMIN_TOKEN" "GET" "/ops/risk/daily-compare?real_only=true" "200" "admin can read daily compare"
expect_status "$USER1_TOKEN" "GET" "/ops/risk/daily-compare?real_only=true" "403" "trader blocked daily compare"

echo
echo "[D] Disabled role enforcement"
if [[ -n "$DISABLED_EMAIL" && -n "$DISABLED_PASSWORD" ]]; then
  disabled_login=$(curl -sS -o /tmp/perm_disabled_body.json -w "%{http_code}" -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=${DISABLED_EMAIL}&password=${DISABLED_PASSWORD}" || true)
  disabled_body=$(cat /tmp/perm_disabled_body.json 2>/dev/null || true)
  if [[ "$disabled_login" == "403" && "$disabled_body" == *"User is disabled"* ]]; then
    pass "disabled user login blocked"
  else
    fail "disabled user login expected 403/User is disabled, got=$disabled_login body=$disabled_body"
  fi
else
  echo "INFO | disabled user creds not provided, skipping disabled login check"
fi

echo
echo "Summary: PASS=$pass_count FAIL=$fail_count"
if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi

