# Checklist Operativa 1 Pagina - Crypto SaaS

Uso: ejecucion diaria (staging/prod) con control rapido de seguridad y operacion.

## A) Pre-operacion

- [ ] `BASE_URL` correcto (staging/prod).
- [ ] API responde `GET /healthz`.
- [ ] Usuario operador autenticado (`TOKEN` valido).
- [ ] (Si aplica) 2FA operativo.
- [ ] Secretos de exchange configurados (`GET /users/exchange-secrets`).

## B) Prueba de ejecucion segura

- [ ] Dry-run OK:
  - `POST /ops/execution/prepare`
- [ ] Binance testnet validado:
  - `POST /ops/execution/binance/test-order`
- [ ] IBKR paper-check validado:
  - `POST /ops/execution/ibkr/paper-check`

## C) Auditoria minima obligatoria

- [ ] `auth.login.success`
- [ ] `execution.prepare`
- [ ] `execution.binance.test_order.success` o `execution.binance.test_order.error`
- [ ] `execution.ibkr.paper_check`

Consulta:

```bash
curl -s "$BASE_URL/ops/audit/me?limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

## D) Rotacion de clave (solo ventana de cambio)

- [ ] Dry run ejecutado:
  - `POST /ops/security/reencrypt-exchange-secrets` (`dry_run=true`)
- [ ] Resultado valido (`updated == scanned`)
- [ ] Re-cifrado aplicado:
  - `POST /ops/security/reencrypt-exchange-secrets` (`dry_run=false`)
- [ ] `ENCRYPTION_KEY` actualizado en Secret Manager
- [ ] API/worker reiniciados
- [ ] Pruebas post-rotacion OK (seccion B)
- [ ] Evento auditado:
  - `security.key_rotation.reencrypt`

## E) Incidentes y rollback

- [ ] Si falla descifrado: restaurar `ENCRYPTION_KEY` anterior.
- [ ] Reiniciar API/worker.
- [ ] Repetir dry-run + Binance testnet.
- [ ] Registrar incidente y bloquear cambios hasta RCA.

## F) Cierre diario

- [ ] Health OK.
- [ ] Pruebas de ejecucion seguras OK.
- [ ] Auditoria validada.
- [ ] Sin secretos expuestos en logs/tickets/chat.
- [ ] Registro de cierre (fecha/hora, operador, resultado).
