# Backend Definition of Done (DoD)

Fecha de corte: 2026-03-01

Este checklist define cuando el backend se considera cerrado para la fase actual.

## 1) Plataforma y despliegue

- [x] API en Render estable (`/healthz` responde `{"status":"ok"}`).
- [x] Deploy reproducible desde `main`.
- [x] Variables de entorno base configuradas (`DATABASE_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`).

## 2) Seguridad base

- [x] JWT login operativo.
- [x] JWT con `access + refresh`, rotación y revocación de sesión (`logout`, `revoke-all`).
- [x] 2FA habilitable por usuario.
- [x] Forzado de 2FA para admins disponible por configuración.
- [x] Política de expiración de password disponible por configuración.
- [x] Secretos de exchange cifrados en reposo.
- [x] Auditoría de eventos críticos.
- [x] Export de auditoría verificable (JSON + `payload_sha256` + `signature_hmac_sha256`).

## 3) Gestión de usuarios (sin SQL manual)

- [x] Crear usuario.
- [x] Cambiar rol (`admin|operator|viewer|trader|disabled`).
- [x] Cambiar email.
- [x] Cambiar password.
- [x] Asignar/limpiar perfil de riesgo.
- [x] Guardar/eliminar secretos BINANCE/IBKR por usuario.
- [x] Guardrails:
  - [x] No degradar/deshabilitar último admin.
  - [x] Admin no puede quitarse su propio rol admin.

## 4) Operación y control de riesgo

- [x] Pretrade checks por exchange y estrategia.
- [x] Exit checks por exchange y estrategia.
- [x] Segregación por exchange vía strategy assignments.
- [x] Kill-switch global de trading (`trading_enabled`) con control admin.
- [x] Límites de exposición agregada (símbolo/exchange) en validaciones de ejecución.
- [x] Idempotencia en endpoints críticos de ejecución/posiciones (`X-Idempotency-Key`).
- [x] Dashboard operativo consolidado (`/ops/dashboard`).
- [x] Tabla consolidada de readiness por usuario (READY/MISSING + razón).

## 5) Automatización operativa

- [x] `Smoke Prod` con artefactos e incidente automático.
- [x] `Dual Ops Daily` con retry y auto-remediation opcional.
- [x] `Security Posture Daily` con artefacto y regla preventiva.
- [x] `Permissions Matrix Daily` para control de autorización por rol.
- [x] `Cleanup Smoke Users Weekly`.
- [x] `Quarterly Rotation` con validación/rollback.

## 6) SaaS-ready backend (baseline mínima)

- [x] `tenant_id` en entidades clave de identidad (`users`) y claim `tid` en JWT.
- [x] Aislamiento por tenant en backoffice/admin principal (`users`, `ops`).
- [x] RBAC por tenant operativo:
  - [x] `admin` (control total),
  - [x] `operator` (operación/lectura),
  - [x] `viewer` (solo lectura),
  - [x] `trader`,
  - [x] `disabled`.
- [x] Endpoints de backoffice de solo lectura por tenant (`/ops/backoffice/*`).

## 7) Pendiente para cierre total de fase

- [ ] Activación de IBKR real para usuario operativo (pendiente aprobación externa de cuenta).
- [ ] Validación final IBKR real: `pretrade + test-order + exit-check`.
- [ ] Cierre del issue IBKR en GitHub tras validación exitosa.

## 8) Criterio de cierre

El backend se declara **cerrado para esta fase** cuando:

1. Todos los puntos 1–6 estén en `[x]` (actualmente cumplido).
2. Los tres puntos de la sección 7 estén en `[x]` (pendiente externo IBKR).

## 9) Estado actual

- Backend **congelado en baseline v1** para operación conservadora SaaS.
- Único bloqueo externo: habilitación final de IBKR real.
