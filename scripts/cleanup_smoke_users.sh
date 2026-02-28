#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ADMIN_OTP="${ADMIN_OTP:-}"
ADMIN_TOTP_SECRET="${ADMIN_TOTP_SECRET:-}"
OLDER_THAN_DAYS="${OLDER_THAN_DAYS:-14}"
DRY_RUN="${DRY_RUN:-false}"

if [[ -z "$BASE_URL" || -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
  echo "BASE_URL, ADMIN_EMAIL and ADMIN_PASSWORD are required"
  exit 1
fi

generate_totp() {
  local secret="$1"
  python3 - "$secret" <<'PY'
import base64, binascii, hashlib, hmac, struct, sys, time
from urllib.parse import parse_qs, urlparse
secret = (sys.argv[1] or "").strip().replace(" ", "").upper()
if not secret:
    print("")
    raise SystemExit(0)
if secret.startswith("OTPAUTH://"):
    parsed = urlparse(secret)
    secret = (parse_qs(parsed.query).get("secret", [""])[0] or "").strip().replace(" ", "").upper()
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

login() {
  local data="username=$ADMIN_EMAIL&password=$ADMIN_PASSWORD"
  if [[ -n "$ADMIN_OTP" ]]; then
    data="${data}&otp=$ADMIN_OTP"
  fi
  local resp token
  resp=$(curl -sS -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "$data" || true)
  token=$(echo "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("access_token",""))' 2>/dev/null || true)
  if [[ "${#token}" -le 100 && -n "$ADMIN_TOTP_SECRET" ]]; then
    ADMIN_OTP=$(generate_totp "$ADMIN_TOTP_SECRET")
    if [[ -n "$ADMIN_OTP" ]]; then
      data="username=$ADMIN_EMAIL&password=$ADMIN_PASSWORD&otp=$ADMIN_OTP"
      resp=$(curl -sS -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data "$data" || true)
      token=$(echo "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("access_token",""))' 2>/dev/null || true)
    fi
  fi
  echo "$token"
}

echo "== Cleanup Smoke Users =="
echo "BASE_URL=$BASE_URL"
echo "OLDER_THAN_DAYS=$OLDER_THAN_DAYS"
echo "DRY_RUN=$DRY_RUN"

TOKEN=$(login)
if [[ "${#TOKEN}" -le 100 ]]; then
  echo "FAIL | admin login failed"
  exit 1
fi
echo "PASS | admin login"

resp=$(curl -sS -X POST "$BASE_URL/ops/admin/cleanup-smoke-users?dry_run=$DRY_RUN&older_than_days=$OLDER_THAN_DAYS" \
  -H "Authorization: Bearer $TOKEN" || true)
echo "$resp" > cleanup_smoke_users_output.json

if [[ "${resp:0:1}" != "{" ]]; then
  echo "FAIL | cleanup endpoint failed: $resp"
  exit 1
fi

summary=$(echo "$resp" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("PASS | cleanup scanned={} eligible={} deleted={} dry_run={}".format(
    d.get("scanned", 0),
    d.get("eligible", 0),
    d.get("deleted", 0),
    d.get("dry_run", True),
))
')
echo "$summary"
