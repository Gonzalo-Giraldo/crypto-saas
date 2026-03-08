# Runbook Disaster Recovery (Backup/Restore DB)

Fecha: 2026-03-08
Aplicacion: crypto-saas-api

## 1) Objetivo
- Ejecutar backup y restore de PostgreSQL con controles de seguridad.
- Evitar errores operativos en restauracion accidental.

## 2) Prerrequisitos
- Variables:
  - `DATABASE_URL` con acceso valido a PostgreSQL.
- Binarios:
  - `pg_dump`, `pg_restore`, `psql`
  - `shasum` o `sha256sum`
  - `openssl` (solo si backup cifrado)

## 3) Backup

### 3.1 Dry-run (obligatorio antes de primer uso)
```bash
export DATABASE_URL='postgresql://...'
DRY_RUN=true BACKUP_FORMAT=custom scripts/backup_db.sh
```

### 3.2 Backup real (formato custom recomendado)
```bash
export DATABASE_URL='postgresql://...'
BACKUP_FORMAT=custom KEEP_LAST=14 scripts/backup_db.sh
```

Salida esperada:
- archivo `.dump` (o `.sql/.sql.gz` si `BACKUP_FORMAT=plain`)
- archivo de integridad `.sha256`

### 3.3 Backup real cifrado (opcional)
```bash
export DATABASE_URL='postgresql://...'
export BACKUP_PASSPHRASE='cambiar-por-secreto-seguro'
ENCRYPT_BACKUP=true BACKUP_FORMAT=custom scripts/backup_db.sh
```

## 4) Restore

### 4.1 Dry-run de restore
```bash
export DATABASE_URL='postgresql://...'
BACKUP_FILE='./backups/crypto_saas_YYYYMMDDTHHMMSSZ.dump' \
DRY_RUN=true \
scripts/restore_db.sh
```

### 4.2 Restore real (requiere confirmacion explicita)
```bash
export DATABASE_URL='postgresql://...'
BACKUP_FILE='./backups/crypto_saas_YYYYMMDDTHHMMSSZ.dump' \
CONFIRM_RESTORE=YES \
scripts/restore_db.sh
```

### 4.3 Restore de backup cifrado
```bash
export DATABASE_URL='postgresql://...'
export BACKUP_PASSPHRASE='cambiar-por-secreto-seguro'
BACKUP_FILE='./backups/crypto_saas_YYYYMMDDTHHMMSSZ.dump.enc' \
CONFIRM_RESTORE=YES \
scripts/restore_db.sh
```

## 5) Guardrails implementados
- `set -euo pipefail` en ambos scripts.
- Validacion de variables requeridas.
- `DRY_RUN=true|false`.
- Restore bloqueado sin `CONFIRM_RESTORE=YES`.
- Verificacion checksum si existe `.sha256`.
- Soporte de backup cifrado (`openssl` AES-256-CBC + PBKDF2).

## 6) Validacion post-restore
- `GET /healthz` debe responder `{"status":"ok"}`.
- Correr smoke:
```bash
BASE_URL='https://...onrender.com' scripts/smoke_prod.sh
```
- Verificar tablas criticas y endpoints admin/readiness.

## 7) Recomendacion operativa
- Ejecutar backup diario y antes de cambios sensibles (rotaciones, migraciones).
- Conservar al menos 14 backups (`KEEP_LAST=14`).
- Guardar passphrase en gestor de secretos, nunca en texto plano del repo.

## 8) Registro de simulacro DR (obligatorio)
- Frecuencia minima: mensual (dry-run) y trimestral (restore controlado).
- Registrar:
  - fecha/hora,
  - operador,
  - entorno,
  - backup usado,
  - resultado (`OK`/`FAIL`),
  - tiempo total de recuperacion observado (RTO),
  - punto de datos recuperado observado (RPO).

Plantilla rapida:
```text
Fecha:
Operador:
Entorno:
Backup file:
Checksum verificado: SI/NO
Restore resultado: OK/FAIL
RTO observado:
RPO observado:
Notas:
```
