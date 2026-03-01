# IBKR Real Go-Live Checklist (Paquete de Arranque)

Fecha: 2026-03-01  
Uso: ejecutar solo cuando IBKR apruebe cuenta operativa real.

## 1) Precondiciones (debe estar todo en OK)

- [ ] Cuenta IBKR real aprobada y activa.
- [ ] Usuario operativo IBKR definido: `gonzalo.giraldo.r@gmail.com`.
- [ ] Segregacion de exchange confirmada:
  - [ ] Gmail: `IBKR enabled`, `BINANCE disabled`.
  - [ ] Yahoo: `BINANCE enabled`, `IBKR disabled`.
- [ ] Workflows en verde antes de iniciar:
  - [ ] `Integration Tests`
  - [ ] `Permissions Matrix`
  - [ ] `Security Posture Daily`
- [ ] Kill-switch global en `true` antes de validar (`/ops/admin/trading-control`).

## 2) Secrets a cargar (GitHub Actions)

En `Settings -> Secrets and variables -> Actions`:

- `DUAL_USER1_EMAIL = gonzalo.giraldo.r@gmail.com`
- `DUAL_USER1_PASSWORD = <password real gmail>`
- `DUAL_USER1_TOTP_SECRET = <secret base32 real gmail>`
- `DUAL_USER2_EMAIL = gonzalogiraldo@yahoo.com`
- `DUAL_USER2_PASSWORD = <password real yahoo>`
- `DUAL_USER2_TOTP_SECRET = <secret base32 real yahoo>`

IBKR real:

- `DUAL_USER1_IBKR_API_KEY = <ibkr real api key>`
- `DUAL_USER1_IBKR_API_SECRET = <ibkr real api secret>`

Opcional rotacion:

- `ROTATE_USER2_IBKR_API_KEY`, `ROTATE_USER2_IBKR_API_SECRET`
- `ROLLBACK_USER2_IBKR_API_KEY`, `ROLLBACK_USER2_IBKR_API_SECRET`

## 3) Configuracion operativa obligatoria (admin)

1. Verificar asignaciones:
   - `GET /ops/strategy/assignments` debe mostrar:
     - Gmail: `IBKR true`, `BINANCE false`.
     - Yahoo: `BINANCE true`, `IBKR false`.
2. Verificar secrets por usuario:
   - Gmail con secreto IBKR cargado.
   - Yahoo sin secreto IBKR.
3. Verificar posture:
   - `GET /ops/security/posture?real_only=true&max_secret_age_days=30`
   - esperado: `users_missing_2fa = 0`.

## 4) Prueba funcional IBKR real (orden)

Con token del usuario Gmail (`TOKEN_G`):

1. Pretrade:
```bash
curl -s -X POST "$BASE_URL/ops/execution/pretrade/ibkr/check" \
  -H "Authorization: Bearer $TOKEN_G" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"AAPL","side":"BUY","qty":1,"rr_estimate":1.6,"trend_tf":"1D","signal_tf":"1H","timing_tf":"15M","in_rth":true,"macro_event_block":false,"earnings_within_24h":false}'
```

2. Test-order:
```bash
curl -s -X POST "$BASE_URL/ops/execution/ibkr/test-order" \
  -H "Authorization: Bearer $TOKEN_G" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"AAPL","side":"BUY","qty":1}'
```

3. Exit-check:
```bash
curl -s -X POST "$BASE_URL/ops/execution/exit/ibkr/check" \
  -H "Authorization: Bearer $TOKEN_G" \
  -H "Content-Type: application/json" \
  --data '{"symbol":"AAPL","side":"BUY","entry_price":180,"current_price":179,"stop_loss":178,"take_profit":183,"opened_minutes":500,"trend_break":false,"signal_reverse":false,"macro_event_block":true,"earnings_within_24h":false}'
```

Criterio de OK:
- pretrade responde sin bloqueos de credenciales,
- test-order responde `sent=true` (o respuesta controlada del bridge real),
- exit-check responde estructura valida con `should_exit`.

## 5) Validacion de segregacion (obligatoria)

- [ ] Gmail no puede ejecutar BINANCE (debe bloquear por exchange disabled).
- [ ] Yahoo no puede ejecutar IBKR (debe bloquear por exchange disabled).

## 6) Evidencia y cierre

- [ ] Guardar run de workflows:
  - [ ] `Dual Ops Daily` (verde)
  - [ ] `Permissions Matrix` (verde)
  - [ ] `Security Posture Daily` (verde)
- [ ] Guardar export de auditoria verificable:
  - `GET /ops/admin/audit/export?limit=500`
- [ ] Cerrar issue `IBKR credentials` (#6) con enlaces de evidencia.

## 7) Rollback rapido (si falla)

1. Activar kill-switch:
   - `POST /ops/admin/trading-control` con `trading_enabled=false`.
2. Restaurar secrets previos IBKR (si aplica).
3. Ejecutar `Dual Ops Daily` para confirmar recuperacion.
4. Abrir/actualizar incidente con causa y accion siguiente.
