# Runbook Produccion - Crypto SaaS

Este runbook define una operacion segura en staging/produccion con:
- secretos gestionados por Secret Manager,
- controles de cambio,
- validaciones post-despliegue,
- rollback operativo.

## 1) Alcance y reglas

- Nunca operar con credenciales en texto plano fuera del Secret Manager.
- Nunca exponer `ENCRYPTION_KEY` en tickets, logs o chat.
- Toda rotacion de clave se ejecuta con ventana de cambio y plan de rollback.
- Toda prueba de exchange en produccion debe ser no destructiva:
  - Binance: `order/test`.
  - IBKR: `test-order` (simulado o bridge paper).

## 2) Variables requeridas (inyectadas por plataforma)

- `DATABASE_URL`
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `BINANCE_TESTNET_BASE_URL`
- `IBKR_BRIDGE_BASE_URL` (opcional)
- `RISK_PROFILE_MODEL2_EMAIL` (email del usuario 1)
- `RISK_PROFILE_LOOSE_EMAIL` (email del usuario 2)

Nota:
- En produccion real, si se habilita Binance live, usar `BINANCE_BASE_URL` separado y controlado por feature flag.

## 3) Flujo de despliegue seguro

1. Preparar release branch y changelog.
2. Aplicar despliegue a staging.
3. Ejecutar smoke tests.
4. Validar auditoria en staging.
5. Aprobar cambio.
6. Desplegar a produccion.
7. Ejecutar smoke tests de produccion.

## 4) Smoke tests (staging/prod)

### 4.1 Health

```bash
curl -s "$BASE_URL/healthz"
```

### 4.2 Login

```bash
export TOKEN=$(
  curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=$EMAIL&password=$PASSWORD" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
)
```

Si 2FA esta habilitado:

```bash
export TOKEN=$(
  curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=$EMAIL&password=$PASSWORD&otp=$OTP" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
)
```

### 4.3 Estado de secretos

```bash
curl -s "$BASE_URL/users/exchange-secrets" \
  -H "Authorization: Bearer $TOKEN"
```

### 4.4 Dry-run de ejecucion

```bash
curl -s -X POST "$BASE_URL/ops/execution/prepare" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"exchange":"BINANCE","symbol":"BTCUSDT","side":"BUY","qty":0.01}'
```

### 4.5 Binance testnet

```bash
curl -s -X POST "$BASE_URL/ops/execution/binance/test-order" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"BTCUSDT","side":"BUY","qty":0.01}'
```

### 4.6 IBKR test-order (paper/simulado)

```bash
curl -s -X POST "$BASE_URL/ops/execution/ibkr/test-order" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"AAPL","side":"BUY","qty":1}'
```

## 5) Auditoria obligatoria

Revisar eventos del operador:

```bash
curl -s "$BASE_URL/ops/audit/me?limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

Eventos esperados despues de pruebas:
- `auth.login.success`
- `execution.prepare`
- `execution.binance.test_order.success` o `.error`
- `execution.ibkr.test_order.success` o `.error`

Comparativo diario (admin):

```bash
curl -s "$BASE_URL/ops/risk/daily-compare" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## 6) Rotacion de clave de cifrado (cambio controlado)

Precondiciones:
- Ventana de cambio aprobada.
- Backup reciente.
- Clave nueva creada en Secret Manager.
- Operador admin autenticado.

### 6.1 Dry run

```bash
curl -s -X POST "$BASE_URL/ops/security/reencrypt-exchange-secrets" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"old_key\":\"$OLD_KEY\",\"new_key\":\"$NEW_KEY\",\"dry_run\":true}"
```

Validar:
- `scanned > 0`
- `updated == scanned`

### 6.2 Aplicar re-cifrado

```bash
curl -s -X POST "$BASE_URL/ops/security/reencrypt-exchange-secrets" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"old_key\":\"$OLD_KEY\",\"new_key\":\"$NEW_KEY\",\"dry_run\":false}"
```

### 6.3 Actualizar runtime

1. Actualizar `ENCRYPTION_KEY` en Secret Manager (target environment).
2. Reiniciar API/worker.
3. Repetir smoke tests de ejecucion.
4. Validar auditoria `security.key_rotation.reencrypt`.

## 7) Rollback

Si falla descifrado o ejecucion tras rotacion:
1. Restaurar `ENCRYPTION_KEY` anterior en Secret Manager.
2. Reiniciar API/worker.
3. Repetir:
  - `POST /ops/execution/prepare`
  - `POST /ops/execution/binance/test-order`
4. Registrar incidente y bloquear nuevos cambios hasta RCA.

## 8) Checklist de cierre

1. Health OK.
2. Login OK.
3. Secretos configurados visibles como `configured`.
4. Dry-run OK.
5. Binance testnet e IBKR test-order validados.
6. Auditoria validada.
7. Si hubo rotacion: validacion post-rotacion y evidencia de rollback plan.

## 9) Automatizacion recomendada

Script rapido de smoke:

```bash
BASE_URL="https://tu-api" \
EMAIL="operador@example.com" \
PASSWORD="***" \
ALLOW_BINANCE_TEST_ERROR=true \
REQUIRE_IBKR_SECRET=false \
scripts/smoke_prod.sh
```

Opciones utiles:
- `TOKEN`: usar token ya emitido (evita login).
- `OTP`: incluir codigo 2FA para login.
- `REQUIRE_IBKR_SECRET=true`: falla si no hay secreto IBKR.

GitHub Actions:
- Workflow: `.github/workflows/smoke-prod.yml`
- Secrets requeridos:
  - `SMOKE_BASE_URL`
  - `SMOKE_PASSWORD`
  - `SMOKE_BINANCE_API_KEY`
  - `SMOKE_BINANCE_API_SECRET`
- Secret opcional:
  - `RENDER_DEPLOY_HOOK_URL` (auto-remediacion: redeploy + reintento smoke)
