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

Solo usuarios reales (sin smoke/disabled/example):

```bash
curl -s "$BASE_URL/ops/risk/daily-compare?real_only=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Postura de seguridad diaria (admin):

```bash
curl -s "$BASE_URL/ops/security/posture?real_only=true&max_secret_age_days=30" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Dashboard operativo (admin):

```bash
curl -s "$BASE_URL/ops/dashboard/summary?real_only=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Filtros opcionales:
- `email_contains=<texto>`
- `exchange=ALL|BINANCE|IBKR`

UI web:
- abrir `https://TU_BASE_URL/ops/dashboard`
- pegar bearer token admin
- cargar estado unificado de operacion + seguridad.
- boton `Open Incident` abre issue prellenado en GitHub.

Asignacion de estrategia (admin):

```bash
curl -s -X POST "$BASE_URL/ops/strategy/assign" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"user_email":"usuario@dominio.com","exchange":"BINANCE","strategy_id":"SWING_V1","enabled":true}'
```

Pre-trade check por exchange:

```bash
curl -s -X POST "$BASE_URL/ops/execution/pretrade/binance/check" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"BTCUSDT","side":"BUY","qty":0.01,"rr_estimate":1.6,"trend_tf":"4H","signal_tf":"1H","timing_tf":"15M","spread_bps":7,"slippage_bps":10,"volume_24h_usdt":90000000}'
```

Ejemplo IBKR (SWING_V1):

```bash
curl -s -X POST "$BASE_URL/ops/execution/pretrade/ibkr/check" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"AAPL","side":"BUY","qty":1,"rr_estimate":1.6,"trend_tf":"1D","signal_tf":"1H","timing_tf":"15M","in_rth":true,"macro_event_block":false,"earnings_within_24h":false}'
```

Exit check por exchange:

```bash
curl -s -X POST "$BASE_URL/ops/execution/exit/binance/check" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"BTCUSDT","side":"BUY","entry_price":50000,"current_price":50750,"stop_loss":49500,"take_profit":51000,"opened_minutes":180,"trend_break":false,"signal_reverse":false}'
```

```bash
curl -s -X POST "$BASE_URL/ops/execution/exit/ibkr/check" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"AAPL","side":"BUY","entry_price":180,"current_price":179,"stop_loss":178,"take_profit":183,"opened_minutes":500,"trend_break":false,"signal_reverse":false,"macro_event_block":true,"earnings_within_24h":false}'
```

Segregacion operativa recomendada (2 usuarios):

```bash
# Usuario Binance (habilitado BINANCE, deshabilitado IBKR)
curl -s -X POST "$BASE_URL/ops/strategy/assign" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"user_email":"usuario_binance@dominio.com","exchange":"BINANCE","strategy_id":"SWING_V1","enabled":true}'
curl -s -X POST "$BASE_URL/ops/strategy/assign" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"user_email":"usuario_binance@dominio.com","exchange":"IBKR","strategy_id":"SWING_V1","enabled":false}'

# Usuario IBKR (habilitado IBKR, deshabilitado BINANCE)
curl -s -X POST "$BASE_URL/ops/strategy/assign" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"user_email":"usuario_ibkr@dominio.com","exchange":"IBKR","strategy_id":"SWING_V1","enabled":true}'
curl -s -X POST "$BASE_URL/ops/strategy/assign" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"user_email":"usuario_ibkr@dominio.com","exchange":"BINANCE","strategy_id":"SWING_V1","enabled":false}'
```

Nota:
- Con esta segregacion, la API bloquea `exchange-secrets` y `execution` cuando el exchange esta deshabilitado para el usuario.

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

Nota para usuarios con 2FA en workflows:
- No usar OTP fijo para jobs diarios.
- Usar secrets tipo semilla TOTP:
  - `DUAL_USER1_TOTP_SECRET`
  - `DUAL_USER2_TOTP_SECRET`
  - `DUAL_ADMIN_TOTP_SECRET` (si aplica)
- El workflow genera OTP automaticamente en cada ejecucion.

Chequeo diario de postura de seguridad:
- Workflow: `.github/workflows/security-posture-daily.yml`
- Objetivo:
  - detectar usuarios operativos sin 2FA,
  - detectar secretos de exchange envejecidos (`max_secret_age_days`),
  - abrir incidente solo en fallo y cerrar automaticamente en recuperacion.

Hardening opcional de login:
- `ENFORCE_2FA_FOR_ADMINS=true`
- `ENFORCE_2FA_EMAILS=email1@dominio.com,email2@dominio.com`

Recomendacion de activacion:
1. Habilitar 2FA en cuentas objetivo.
2. Verificar `GET /ops/security/posture` sin pendientes.
3. Activar variables de enforcement.

Rotacion trimestral automatizada:
- Workflow: `.github/workflows/quarterly-rotation.yml`
- Script: `scripts/quarterly_rotation.sh`
- El workflow:
  - abre/actualiza checklist trimestral automaticamente,
  - aplica nuevas credenciales (`ROTATE_*`) si estan cargadas,
  - ejecuta validacion automatica post-rotacion,
  - si falla y hay `ROLLBACK_*`, aplica rollback automatico y revalida,
  - abre incidente si no se recupera.

Secrets para rotacion:
- Nuevas credenciales:
  - `ROTATE_USER1_BINANCE_API_KEY`
  - `ROTATE_USER1_BINANCE_API_SECRET`
  - `ROTATE_USER2_IBKR_API_KEY`
  - `ROTATE_USER2_IBKR_API_SECRET`
- Credenciales previas para rollback:
  - `ROLLBACK_USER1_BINANCE_API_KEY`
  - `ROLLBACK_USER1_BINANCE_API_SECRET`
  - `ROLLBACK_USER2_IBKR_API_KEY`
  - `ROLLBACK_USER2_IBKR_API_SECRET`
