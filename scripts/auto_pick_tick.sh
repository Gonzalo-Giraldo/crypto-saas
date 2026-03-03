#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ADMIN_OTP="${ADMIN_OTP:-}"
ADMIN_TOTP_SECRET="${ADMIN_TOTP_SECRET:-}"
TOP_N="${TOP_N:-10}"
DRY_RUN="${DRY_RUN:-true}"
REAL_ONLY="${REAL_ONLY:-true}"
INCLUDE_SERVICE_USERS="${INCLUDE_SERVICE_USERS:-false}"

pass_count=0
fail_count=0

pass() { echo "PASS | $1"; pass_count=$((pass_count + 1)); }
fail() { echo "FAIL | $1"; fail_count=$((fail_count + 1)); }

generate_totp() {
  local secret="$1"
  python3 - "$secret" <<'PY'
import base64, hashlib, hmac, struct, sys, time
from urllib.parse import urlparse, parse_qs

secret = (sys.argv[1] or "").strip()
if not secret:
    print("")
    raise SystemExit(0)

upper = secret.upper()
if upper.startswith("OTPAUTH://"):
    qs = parse_qs(urlparse(secret).query)
    secret = (qs.get("secret", [""])[0]).strip()
elif "SECRET=" in upper:
    secret = upper.split("SECRET=", 1)[1].split("&", 1)[0].strip()

if not secret:
    print("")
    raise SystemExit(0)

secret = "".join(ch for ch in secret.upper() if ch.isalnum())
pad = "=" * ((8 - len(secret) % 8) % 8)
key = base64.b32decode(secret + pad, casefold=True)
counter = int(time.time()) // 30
msg = struct.pack(">Q", counter)
digest = hmac.new(key, msg, hashlib.sha1).digest()
offset = digest[-1] & 0x0F
code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
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
    --data "$data"
}

echo "== Auto Pick Tick =="
echo "BASE_URL=${BASE_URL}"
echo "TOP_N=${TOP_N} DRY_RUN=${DRY_RUN} REAL_ONLY=${REAL_ONLY} INCLUDE_SERVICE_USERS=${INCLUDE_SERVICE_USERS}"

if [[ -z "$BASE_URL" ]]; then
  fail "Missing BASE_URL"
  echo "Summary: PASS=${pass_count} FAIL=${fail_count}"
  exit 1
fi
if [[ -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
  fail "Missing ADMIN_EMAIL / ADMIN_PASSWORD"
  echo "Summary: PASS=${pass_count} FAIL=${fail_count}"
  exit 1
fi

if curl -sS "$BASE_URL/healthz" | grep -q '"status":"ok"'; then
  pass "healthz"
else
  fail "healthz"
fi

admin_resp="$(login_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD" "$ADMIN_OTP")"
admin_token="$(echo "$admin_resp" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null || true)"

if [[ "${#admin_token}" -le 100 && -n "$ADMIN_TOTP_SECRET" ]]; then
  ADMIN_OTP="$(generate_totp "$ADMIN_TOTP_SECRET" || true)"
  if [[ -n "$ADMIN_OTP" ]]; then
    admin_resp="$(login_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD" "$ADMIN_OTP")"
    admin_token="$(echo "$admin_resp" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null || true)"
  fi
fi

if [[ "${#admin_token}" -le 100 ]]; then
  fail "admin login failed: $admin_resp"
  echo "Summary: PASS=${pass_count} FAIL=${fail_count}"
  exit 1
fi
pass "admin login"

tick_url="${BASE_URL}/ops/admin/auto-pick/tick?dry_run=${DRY_RUN}&top_n=${TOP_N}&real_only=${REAL_ONLY}&include_service_users=${INCLUDE_SERVICE_USERS}"
tick_resp="$(curl -sS -X POST "$tick_url" -H "Authorization: Bearer ${admin_token}")"
echo "$tick_resp" > auto_pick_tick_output.json

python3 - "$tick_resp" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
print(
    f"INFO | executed_count={d.get('executed_count',0)} dry_run={d.get('dry_run')} top_n={d.get('top_n')}"
)
for r in d.get("results", [])[:20]:
    print(
        "INFO | "
        f"{r.get('user_email')} {r.get('exchange')} "
        f"decision={r.get('decision')} scanned={r.get('scanned_assets')} "
        f"selected={r.get('selected')} score={r.get('selected_score')}"
    )
PY

executed_count="$(echo "$tick_resp" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("executed_count",0))' 2>/dev/null || echo 0)"
if [[ "${executed_count}" -ge 1 ]]; then
  pass "tick executed_count=${executed_count}"
else
  fail "tick executed_count=${executed_count}"
fi

echo "Summary: PASS=${pass_count} FAIL=${fail_count}"
if [[ "${fail_count}" -gt 0 ]]; then
  exit 1
fi

