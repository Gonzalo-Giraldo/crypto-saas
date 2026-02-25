# Runbook Operativo - Crypto SaaS

Este runbook define una operacion segura para:
- configurar credenciales cifradas,
- ejecutar pruebas en Binance testnet,
- validar IBKR paper-check,
- rotar la clave de cifrado de secretos.

## 0) Prerrequisitos

- API levantada.
- Base de datos levantada.
- Variables de entorno configuradas:
  - `DATABASE_URL`
  - `SECRET_KEY`
  - `ENCRYPTION_KEY`
  - `BINANCE_TESTNET_BASE_URL`

Health check:

```bash
curl -s http://127.0.0.1:8000/healthz
```

## 1) Registrar usuario y login

Define variables de sesion:

```bash
export BASE_URL="http://127.0.0.1:8000"
export EMAIL="operador@example.com"
export PASSWORD="Trader123!"
```

Registrar:

```bash
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  --data "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
```

Login (sin 2FA):

```bash
export TOKEN=$(
  curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=$EMAIL&password=$PASSWORD" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
)
```

Login (con 2FA habilitado):

```bash
export OTP="123456"
export TOKEN=$(
  curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=$EMAIL&password=$PASSWORD&otp=$OTP" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
)
```

## 2) Guardar credenciales cifradas de exchange

### Binance

```bash
curl -s -X POST "$BASE_URL/users/exchange-secrets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"exchange":"BINANCE","api_key":"TU_BINANCE_API_KEY","api_secret":"TU_BINANCE_API_SECRET"}'
```

### IBKR

```bash
curl -s -X POST "$BASE_URL/users/exchange-secrets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"exchange":"IBKR","api_key":"TU_IBKR_API_KEY","api_secret":"TU_IBKR_API_SECRET"}'
```

Ver credenciales configuradas (sin exponer secretos):

```bash
curl -s "$BASE_URL/users/exchange-secrets" \
  -H "Authorization: Bearer $TOKEN"
```

## 3) Ejecucion segura (sin dinero real)

### 3.1 Dry-run de preparacion

```bash
curl -s -X POST "$BASE_URL/ops/execution/prepare" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"exchange":"BINANCE","symbol":"BTCUSDT","side":"BUY","qty":0.01}'
```

### 3.2 Binance testnet order/test

```bash
curl -s -X POST "$BASE_URL/ops/execution/binance/test-order" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"BTCUSDT","side":"BUY","qty":0.01}'
```

### 3.3 IBKR paper-check

```bash
curl -s -X POST "$BASE_URL/ops/execution/ibkr/paper-check" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"AAPL","side":"BUY","qty":1}'
```

## 4) Auditoria operativa

Eventos del usuario actual:

```bash
curl -s "$BASE_URL/ops/audit/me?limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

Eventos globales (solo admin):

```bash
curl -s "$BASE_URL/ops/audit/all?limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

## 5) Rotacion de clave de cifrado

Importante:
- Primero ejecutar `dry_run=true`.
- Luego ejecutar `dry_run=false`.
- Finalmente actualizar `ENCRYPTION_KEY` en entorno y reiniciar API.

### 5.1 Dry run

```bash
curl -s -X POST "$BASE_URL/ops/security/reencrypt-exchange-secrets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"old_key":"CLAVE_ANTERIOR","new_key":"CLAVE_NUEVA","dry_run":true}'
```

### 5.2 Aplicar re-cifrado

```bash
curl -s -X POST "$BASE_URL/ops/security/reencrypt-exchange-secrets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"old_key":"CLAVE_ANTERIOR","new_key":"CLAVE_NUEVA","dry_run":false}'
```

### 5.3 Post-rotacion

1. Actualizar `ENCRYPTION_KEY` en `.env`/secret manager.
2. Reiniciar API.
3. Volver a correr:
  - `POST /ops/execution/prepare`
  - `POST /ops/execution/binance/test-order`
4. Revisar auditoria:
  - `security.key_rotation.reencrypt`
  - `execution.prepare`

## 6) Respuesta a incidentes

- Error `Missing credentials for BINANCE/IBKR`:
  - Cargar credenciales en `/users/exchange-secrets`.
- Error Binance 401:
  - Revisar formato/validez de API key.
- Error de descifrado tras rotacion:
  - Restituir `ENCRYPTION_KEY` anterior.
  - Confirmar que `old_key/new_key` del proceso sean correctas.
- Si endpoint falla:
  - Verificar `/healthz`.
  - Revisar auditoria `ops/audit/me`.

## 7) Cierre operativo

Checklist final:
1. Credenciales cifradas configuradas.
2. Dry-run OK.
3. Binance testnet `order/test` OK (o error controlado auditado).
4. IBKR paper-check OK.
5. Auditoria validada.
6. Si hubo rotacion: post-rotacion validada.
