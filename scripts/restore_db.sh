#!/usr/bin/env bash
set -euo pipefail

# Required
DATABASE_URL="${DATABASE_URL:-}"
BACKUP_FILE="${BACKUP_FILE:-}"

# Safety and options
CONFIRM_RESTORE="${CONFIRM_RESTORE:-}"
DRY_RUN="${DRY_RUN:-false}"
RESTORE_CLEAN="${RESTORE_CLEAN:-true}"
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"
CHECKSUM_FILE="${CHECKSUM_FILE:-}"

if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

if [[ -z "$BACKUP_FILE" ]]; then
  echo "BACKUP_FILE is required"
  exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "BACKUP_FILE not found: $BACKUP_FILE"
  exit 1
fi

if [[ "$DRY_RUN" != "true" && "$DRY_RUN" != "false" ]]; then
  echo "DRY_RUN must be true|false"
  exit 1
fi

if [[ "$RESTORE_CLEAN" != "true" && "$RESTORE_CLEAN" != "false" ]]; then
  echo "RESTORE_CLEAN must be true|false"
  exit 1
fi

if [[ "$DRY_RUN" == "false" && "$CONFIRM_RESTORE" != "YES" ]]; then
  echo "Refusing restore. Set CONFIRM_RESTORE=YES to continue."
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

require_cmd pg_restore
require_cmd psql
if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
  echo "Missing required command: sha256sum or shasum"
  exit 1
fi

resolved_checksum_file="$CHECKSUM_FILE"
if [[ -z "$resolved_checksum_file" ]]; then
  if [[ -f "${BACKUP_FILE}.sha256" ]]; then
    resolved_checksum_file="${BACKUP_FILE}.sha256"
  fi
fi

if [[ -n "$resolved_checksum_file" ]]; then
  if [[ ! -f "$resolved_checksum_file" ]]; then
    echo "CHECKSUM_FILE not found: $resolved_checksum_file"
    exit 1
  fi
  expected="$(awk '{print $1}' "$resolved_checksum_file")"
  actual="$(sha256_file "$BACKUP_FILE")"
  if [[ "$expected" != "$actual" ]]; then
    echo "Checksum mismatch for backup file"
    echo "Expected: $expected"
    echo "Actual:   $actual"
    exit 1
  fi
  echo "Checksum verification: OK"
fi

work_file="$BACKUP_FILE"
tmp_file=""

cleanup() {
  if [[ -n "$tmp_file" && -f "$tmp_file" ]]; then
    rm -f "$tmp_file"
  fi
}
trap cleanup EXIT

if [[ "$BACKUP_FILE" == *.enc ]]; then
  if [[ -z "$BACKUP_PASSPHRASE" ]]; then
    echo "BACKUP_PASSPHRASE is required for encrypted backups (.enc)"
    exit 1
  fi
  require_cmd openssl
  tmp_file="$(mktemp)"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY_RUN command: openssl enc -d -aes-256-cbc -pbkdf2 -in \"$BACKUP_FILE\" -out \"$tmp_file\" -pass \"pass:***\""
  else
    openssl enc -d -aes-256-cbc -pbkdf2 \
      -in "$BACKUP_FILE" \
      -out "$tmp_file" \
      -pass "pass:$BACKUP_PASSPHRASE"
  fi
  work_file="$tmp_file"
fi

restore_with_pg_restore() {
  local source_file="$1"
  local clean_args=()
  if [[ "$RESTORE_CLEAN" == "true" ]]; then
    clean_args=(--clean --if-exists)
  fi
  local cmd=(pg_restore "${clean_args[@]}" --no-owner --no-privileges --dbname "$DATABASE_URL" "$source_file")
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY_RUN command: ${cmd[*]}"
    return 0
  fi
  "${cmd[@]}"
}

restore_sql_file() {
  local source_file="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY_RUN command: psql \"$DATABASE_URL\" -f \"$source_file\""
    return 0
  fi
  psql "$DATABASE_URL" -f "$source_file"
}

restore_sql_gz_file() {
  local source_file="$1"
  require_cmd gzip
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY_RUN command: gzip -dc \"$source_file\" | psql \"$DATABASE_URL\""
    return 0
  fi
  gzip -dc "$source_file" | psql "$DATABASE_URL"
}

echo "== Restore DB =="
echo "BACKUP_FILE=$BACKUP_FILE DRY_RUN=$DRY_RUN RESTORE_CLEAN=$RESTORE_CLEAN"

if [[ "$work_file" == *.dump ]]; then
  restore_with_pg_restore "$work_file"
elif [[ "$work_file" == *.sql ]]; then
  restore_sql_file "$work_file"
elif [[ "$work_file" == *.sql.gz ]]; then
  restore_sql_gz_file "$work_file"
else
  # Fallback detection for decrypted temp files without extension.
  if file "$work_file" | grep -qi "PostgreSQL custom database dump"; then
    restore_with_pg_restore "$work_file"
  else
    echo "Unknown backup format for file: $BACKUP_FILE"
    echo "Supported: .dump, .sql, .sql.gz (and encrypted variants with .enc)"
    exit 1
  fi
fi

echo "Restore completed"
