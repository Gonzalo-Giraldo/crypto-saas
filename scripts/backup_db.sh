#!/usr/bin/env bash
set -euo pipefail

# Required
DATABASE_URL="${DATABASE_URL:-}"

# Optional controls
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_PREFIX="${BACKUP_PREFIX:-crypto_saas}"
BACKUP_FORMAT="${BACKUP_FORMAT:-custom}" # custom | plain
COMPRESS_PLAIN_SQL="${COMPRESS_PLAIN_SQL:-true}" # only for plain
ENCRYPT_BACKUP="${ENCRYPT_BACKUP:-false}"
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"
KEEP_LAST="${KEEP_LAST:-0}"
DRY_RUN="${DRY_RUN:-false}"

if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

if [[ "$BACKUP_FORMAT" != "custom" && "$BACKUP_FORMAT" != "plain" ]]; then
  echo "BACKUP_FORMAT must be 'custom' or 'plain'"
  exit 1
fi

if [[ "$ENCRYPT_BACKUP" == "true" && -z "$BACKUP_PASSPHRASE" ]]; then
  echo "BACKUP_PASSPHRASE is required when ENCRYPT_BACKUP=true"
  exit 1
fi

if [[ "$BACKUP_FORMAT" == "plain" && "$COMPRESS_PLAIN_SQL" != "true" && "$COMPRESS_PLAIN_SQL" != "false" ]]; then
  echo "COMPRESS_PLAIN_SQL must be true|false"
  exit 1
fi

if [[ "$DRY_RUN" != "true" && "$DRY_RUN" != "false" ]]; then
  echo "DRY_RUN must be true|false"
  exit 1
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  else
    shasum -a 256 "$file" | awk '{print $1}'
  fi
}

require_cmd pg_dump
if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
  echo "Missing required command: sha256sum or shasum"
  exit 1
fi
if [[ "$BACKUP_FORMAT" == "plain" && "$COMPRESS_PLAIN_SQL" == "true" ]]; then
  require_cmd gzip
fi
if [[ "$ENCRYPT_BACKUP" == "true" ]]; then
  require_cmd openssl
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

if [[ "$BACKUP_FORMAT" == "custom" ]]; then
  backup_file="$BACKUP_DIR/${BACKUP_PREFIX}_${timestamp}.dump"
  dump_cmd=(pg_dump --format=custom --no-owner --no-privileges --file "$backup_file" "$DATABASE_URL")
else
  backup_file="$BACKUP_DIR/${BACKUP_PREFIX}_${timestamp}.sql"
  dump_cmd=(pg_dump --format=plain --no-owner --no-privileges --file "$backup_file" "$DATABASE_URL")
fi

echo "== Backup DB =="
echo "BACKUP_FORMAT=$BACKUP_FORMAT DRY_RUN=$DRY_RUN ENCRYPT_BACKUP=$ENCRYPT_BACKUP"
echo "Output base file: $backup_file"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "DRY_RUN command: ${dump_cmd[*]}"
  exit 0
fi

"${dump_cmd[@]}"

if [[ "$BACKUP_FORMAT" == "plain" && "$COMPRESS_PLAIN_SQL" == "true" ]]; then
  gzip -f "$backup_file"
  backup_file="${backup_file}.gz"
fi

if [[ "$ENCRYPT_BACKUP" == "true" ]]; then
  encrypted_file="${backup_file}.enc"
  openssl enc -aes-256-cbc -pbkdf2 -salt \
    -in "$backup_file" \
    -out "$encrypted_file" \
    -pass "pass:$BACKUP_PASSPHRASE"
  rm -f "$backup_file"
  backup_file="$encrypted_file"
fi

checksum="$(sha256_file "$backup_file")"
checksum_file="${backup_file}.sha256"
printf "%s  %s\n" "$checksum" "$(basename "$backup_file")" > "$checksum_file"

echo "Backup created: $backup_file"
echo "Checksum file: $checksum_file"

if [[ "$KEEP_LAST" =~ ^[0-9]+$ ]] && [[ "$KEEP_LAST" -gt 0 ]]; then
  mapfile -t old_files < <(ls -1t "$BACKUP_DIR/${BACKUP_PREFIX}_"* 2>/dev/null | tail -n +$((KEEP_LAST + 1)) || true)
  if [[ "${#old_files[@]}" -gt 0 ]]; then
    echo "Pruning old backups (KEEP_LAST=$KEEP_LAST)"
    for f in "${old_files[@]}"; do
      rm -f "$f"
      rm -f "${f}.sha256"
      echo "Removed: $f"
    done
  fi
fi
