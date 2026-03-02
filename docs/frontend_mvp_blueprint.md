# Frontend MVP Blueprint (Operacion + Backoffice)

Fecha: 2026-03-01  
Objetivo: definir la primera version de frontend para operar el backend actual sin pasos manuales innecesarios.

## 1) Alcance del MVP

- Autenticacion con 2FA.
- Vista operativa diaria unificada (estado, riesgo, seguridad).
- Gestion de usuarios/roles/perfiles/secretos para admin.
- Monitoreo por tenant (admin/operator/viewer).
- Ejecucion de pruebas no destructivas (pretrade/test-order/exit-check).
- Apertura de incidente y evidencias operativas.

No incluye en esta fase:
- graficas avanzadas de trading,
- motor de estrategias visual,
- billing SaaS,
- soporte multi-tenant comercial completo (solo baseline tecnico ya implementado).

## 2) Roles y permisos UI

- `admin`:
  - acceso total a pantallas y acciones de configuracion.
- `operator`:
  - lectura completa de backoffice + acciones operativas no sensibles.
  - sin cambio de roles, sin cambio de credenciales maestras.
- `viewer`:
  - solo lectura de estado/backoffice.
- `trader`:
  - acciones solo sobre su cuenta (pretrade/test-order/exit-check, posiciones, secrets propios).
- `disabled`:
  - sin acceso.

## 3) Mapa de pantallas (v1)

1. `Login + 2FA`
2. `Operations Home` (dashboard principal)
3. `Users Admin` (solo admin)
4. `User Readiness` (admin/operator/viewer)
5. `Execution Console` (admin/operator/trader)
6. `Audit & Export` (admin)
7. `Settings & Security` (admin)

## 4) Flujo diario (NOC-lite)

1. Login con 2FA.
2. Abrir `Operations Home`.
3. Revisar KPIs:
   - health,
   - users missing 2FA,
   - stale secrets,
   - blocked opens,
   - errors trend.
4. Si rojo/amarillo:
   - abrir incidente desde UI,
   - asignar responsable,
   - ejecutar runbook.
5. Si verde:
   - validar quick checks en `Execution Console`,
   - cerrar ciclo operativo.

## 5) Especificacion por pantalla

## 5.1 Login + 2FA

Entradas:
- email,
- password,
- OTP (si aplica).

Backend:
- `POST /auth/login`

Salida:
- token en memoria de sesion (no localStorage para cuentas admin).

## 5.2 Operations Home

Objetivo:
- estado global de operacion en una sola vista.

Backend:
- `GET /ops/dashboard/summary?real_only=true`
- `GET /ops/backoffice/summary?real_only=true`

Widgets:
- estado global (green/yellow/red),
- seguridad (2FA faltante / secretos vencidos),
- operacion (trades, open positions, blocked),
- tendencia 7 dias,
- productividad por perfil.

Acciones:
- `Open Incident` (atajo a issue GitHub),
- `Refresh`.

## 5.3 Users Admin (admin)

Objetivo:
- gestionar ciclo de vida de usuarios sin SQL.

Backend:
- `GET /users`
- `POST /users`
- `PATCH /users/{id}/role`
- `PATCH /users/{id}/email`
- `PUT /users/{id}/password`
- `PUT /users/{id}/risk-profile`
- `GET /users/risk-profiles`
- `PUT /users/{id}/exchange-secrets`
- `DELETE /users/{id}/exchange-secrets/{exchange}`
- `GET /users/{id}/readiness-check`

Reglas UX:
- confirmar acciones sensibles (role/password/secret delete),
- mostrar resultado de readiness al guardar.

## 5.4 User Readiness

Objetivo:
- detectar bloqueos antes de operar.

Backend:
- `GET /ops/backoffice/users?real_only=true`
- `GET /users/{id}/readiness-check` (detalle por usuario)

Campos:
- role,
- 2FA status,
- exchange enabled/configured,
- READY/MISSING + motivo.

## 5.5 Execution Console

Objetivo:
- pruebas operativas seguras y repetibles.

Backend:
- `POST /ops/execution/pretrade/binance/check`
- `POST /ops/execution/pretrade/ibkr/check`
- `POST /ops/execution/binance/test-order`
- `POST /ops/execution/ibkr/test-order`
- `POST /ops/execution/exit/binance/check`
- `POST /ops/execution/exit/ibkr/check`
- opcional `POST /ops/execution/prepare`

Notas:
- usar `X-Idempotency-Key` por envio.
- mostrar checks detallados y causa de bloqueo.

## 5.6 Audit & Export (admin)

Objetivo:
- evidencia verificable para operacion/compliance.

Backend:
- `GET /ops/audit/me`
- `GET /ops/audit/all`
- `GET /ops/admin/audit/export`

Salida:
- tabla de eventos,
- descarga JSON exportado,
- mostrar `payload_sha256` y `signature_hmac_sha256`.

## 5.7 Settings & Security (admin)

Objetivo:
- controles globales y mantenimiento.

Backend:
- `GET /ops/admin/trading-control`
- `POST /ops/admin/trading-control`
- `GET /ops/admin/idempotency/stats`
- `POST /ops/admin/idempotency/cleanup`
- `GET /ops/security/posture`

Acciones:
- kill-switch ON/OFF,
- limpieza de llaves idempotentes,
- revisión de postura de seguridad.

## 6) Navegacion propuesta

Sidebar:
- Home
- Execution
- Backoffice
- Audit
- Settings

Header:
- tenant actual,
- rol actual,
- usuario actual,
- logout.

## 7) Fase de implementacion sugerida

Sprint A:
- Login + Home + Backoffice readonly.

Sprint B:
- Users Admin + Readiness detallado.

Sprint C:
- Execution Console + Audit Export UI.

Sprint D:
- Settings/Security + pulido final.

## 8) Criterio de aceptacion del frontend MVP

- Todas las acciones del runbook diario se ejecutan desde UI.
- Cero SQL/manual para operacion normal.
- RBAC correcto por rol.
- Trazabilidad completa via auditoria/export.
- Operacion diaria posible en menos de 10 minutos.
