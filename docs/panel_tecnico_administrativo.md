# Panel Tecnico/Administrativo - Propuesta de Implementacion

Fecha: 2026-03-08
Estado: fase 2 inicial implementada en `ops_console_v2.html` (modulo `Control Tecnico`).

## 1) Mapa modular (ownership)

1. `Control Tecnico` - Mixto  
Backend: `/healthz`, `/ops/admin/readiness/daily-gate`, `/ops/security/posture`, `/ops/admin/idempotency/stats`  
Frontend: tarjetas de estado, resumen de continuidad, accesos a runbooks.

2. `Seguridad` - Backend  
Backend: 2FA posture, secretos stale, rotacion, export firmado de auditoria.  
Frontend: panel de alertas y acciones admin.

3. `Operacion` - Mixto  
Backend: trading-control, auto-pick/auto-exit, account-status por broker.  
Frontend: controles de ejecucion y estado por exchange.

4. `Riesgo` - Backend  
Backend: riesgo diario, limites, perfiles y politicas runtime.  
Frontend: tablas comparativas y semaforos.

5. `Usuarios y Gobierno` - Mixto  
Backend: CRUD de usuarios, readiness, cambios sensibles con `reason`.  
Frontend: flujo administrativo guiado y confirmaciones.

6. `Continuidad (DR)` - Mixto  
Backend/DevOps: backup/restore scripts + workflows DR + evidencias.  
Frontend: vista de ultimo simulacro, RTO/RPO, checklist de cierre.

## 2) Fase 1 (ya implementada)
- Consola de 3 pantallas:
  - login,
  - menu principal,
  - detalle por modulo con regreso al menu.
- Nuevo modulo en menu admin/operator:
  - `Control Tecnico`.
- Datos visibles en `Control Tecnico`:
  - estado `healthz`,
  - resultado `daily-gate`,
  - usuarios en alcance / missing 2FA / stale secrets,
  - volumen de registros idempotentes.

## 3) Fase 2 (implementada parcialmente)
- Agregado bloque `Continuidad DR`:
  - snapshot operativo diario,
  - resumen de seguridad (scope, missing 2FA, stale secrets),
  - recordatorio de evidencia RTO/RPO.
- Agregado bloque `CI/Release`:
  - enlaces directos a workflows:
    - Integration Tests,
    - Smoke Prod,
    - DR Drill Monthly.

Pendiente para fase 2 completa:
- consumir estado del ultimo run de workflows via integracion GitHub API (backend proxy interno),
- mostrar ultimo `RUN_ID` y semaforo verde/rojo en vivo.

## 4) Criterio de aceptacion
- El panel permite a un admin tomar decision operativa sin salir de consola:
  - estado tecnico,
  - estado de seguridad,
  - estado de continuidad,
  - evidencia de validacion.
