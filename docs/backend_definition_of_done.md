# Backend Definition of Done (DoD)

Fecha de corte: 2026-03-01

Este checklist define cuando el backend se considera cerrado para la fase actual.

## 1) Plataforma y despliegue

- [x] API en Render estable (`/healthz` responde `{"status":"ok"}`).
- [x] Deploy reproducible desde `main`.
- [x] Variables de entorno base configuradas (`DATABASE_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`).

## 2) Seguridad base

- [x] JWT login operativo.
- [x] 2FA habilitable por usuario.
- [x] Forzado de 2FA para admins disponible por configuración.
- [x] Secretos de exchange cifrados en reposo.
- [x] Auditoría de eventos críticos.

## 3) Gestión de usuarios (sin SQL manual)

- [x] Crear usuario.
- [x] Cambiar rol (`admin|trader|disabled`).
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
- [x] Dashboard operativo consolidado (`/ops/dashboard`).
- [x] Tabla consolidada de readiness por usuario (READY/MISSING + razón).

## 5) Automatización operativa

- [x] `Smoke Prod` con artefactos e incidente automático.
- [x] `Dual Ops Daily` con retry y auto-remediation opcional.
- [x] `Security Posture Daily` con artefacto y regla preventiva.
- [x] `Permissions Matrix Daily` para control de autorización por rol.
- [x] `Cleanup Smoke Users Weekly`.
- [x] `Quarterly Rotation` con validación/rollback.

## 6) Pendiente para cierre total de fase

- [ ] Activación de IBKR real para usuario operativo (pendiente aprobación externa de cuenta).
- [ ] Validación final IBKR real: `pretrade + test-order + exit-check`.
- [ ] Cierre del issue IBKR en GitHub tras validación exitosa.

## Criterio de cierre

El backend se declara **cerrado para esta fase** cuando:

1. Todos los puntos 1–5 estén en `[x]` (actualmente cumplido).
2. Los tres puntos de la sección 6 estén en `[x]` (pendiente externo IBKR).
