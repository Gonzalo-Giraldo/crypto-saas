#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ADMIN_OTP="${ADMIN_OTP:-}"
SECRET_MAX_AGE_DAYS="${SECRET_MAX_AGE_DAYS:-30}"
REAL_ONLY="${REAL_ONLY:-true}"

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

if [[ -z "$BASE_URL" || -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
  echo "BASE_URL, ADMIN_EMAIL and ADMIN_PASSWORD are required"
  exit 1
fi

echo "== Security Posture Daily =="
echo "BASE_URL=$BASE_URL"
echo "REAL_ONLY=$REAL_ONLY"
echo "SECRET_MAX_AGE_DAYS=$SECRET_MAX_AGE_DAYS"

echo
echo "[A] Health"
if health=$(curl -fsS "$BASE_URL/healthz" 2>/dev/null); then
  status=$(echo "$health" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("status",""))')
  if [[ "$status" == "ok" ]]; then
    pass "healthz"
  else
    fail "healthz status=$status"
  fi
else
  fail "healthz unreachable"
fi

echo
echo "[B] Admin login"
login_data="username=$ADMIN_EMAIL&password=$ADMIN_PASSWORD"
if [[ -n "$ADMIN_OTP" ]]; then
  login_data="${login_data}&otp=${ADMIN_OTP}"
fi
login_resp=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "$login_data" || true)
admin_token=$(echo "$login_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("access_token",""))' 2>/dev/null || true)
if [[ "${#admin_token}" -gt 100 ]]; then
  pass "admin login"
else
  fail "admin login failed: $login_resp"
  echo
  echo "Summary: PASS=$pass_count FAIL=$fail_count"
  exit 1
fi

echo
echo "[C] Security posture"
posture_resp=$(curl -sS "$BASE_URL/ops/security/posture?real_only=$REAL_ONLY&max_secret_age_days=$SECRET_MAX_AGE_DAYS" \
  -H "Authorization: Bearer $admin_token" || true)
if [[ "${posture_resp:0:1}" != "{" ]]; then
  fail "security posture request failed: $posture_resp"
  echo
  echo "Summary: PASS=$pass_count FAIL=$fail_count"
  exit 1
fi

total_users=$(echo "$posture_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["summary"]["total_users"])' || echo 0)
missing_2fa=$(echo "$posture_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["summary"]["users_missing_2fa"])' || echo 0)
stale_secrets=$(echo "$posture_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["summary"]["users_with_stale_secrets"])' || echo 0)

if [[ "$total_users" -gt 0 ]]; then
  pass "security posture users=$total_users"
else
  fail "security posture no users in scope"
fi

if [[ "$missing_2fa" -eq 0 ]]; then
  pass "2FA posture ok"
else
  fail "users missing 2FA: $missing_2fa"
fi

if [[ "$stale_secrets" -eq 0 ]]; then
  pass "secret rotation posture ok"
else
  fail "users with stale secrets: $stale_secrets"
fi

echo
echo "Summary: PASS=$pass_count FAIL=$fail_count"
if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
