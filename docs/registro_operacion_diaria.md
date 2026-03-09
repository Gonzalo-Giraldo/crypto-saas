# Registro Operacion Diaria - Crypto SaaS

Uso:
- Completar una fila por dia.
- Adjuntar link del run de GitHub Actions (Smoke Prod).
- Si hubo incidente, agregar resumen corto y estado final.

## Tabla diaria

| Fecha | Hora | Operador | Healthz | Smoke Prod | Auditoria | Incidente | Accion aplicada | Estado final | Link run |
|---|---|---|---|---|---|---|---|---|---|
| 2026-03-09 | 21:10 | Gonzalo | OK | Verde | Temporal (2FA login bypass) | No | Deploy commit `0287401` (`feat(auth): temporary 2FA login bypass with auto-expiry window`); validado ingreso a Ops Console y navegacion por todos los modulos | Cerrado OK | Render vars: `AUTH_2FA_LOGIN_ENABLED=false`, `AUTH_2FA_TEMP_DISABLE_UNTIL_UTC=2026-03-23T23:59:59Z`; reversa: reactivar 2FA el 2026-03-24 UTC |
| 2026-03-08 | 20:10 | Gonzalo | OK | Verde | OK | No | Merge post-release warnings cleanup a `main`; ejecutar smoke post-merge | Cerrado OK | Smoke: https://github.com/Gonzalo-Giraldo/crypto-saas/actions/runs/03629f1 |
| 2026-03-08 | 19:30 | Gonzalo | OK | Verde | OK | No | Cierre release M1..M11 + validacion Integration/Smoke + ajuste TOTP admin fallback | Cerrado OK | Integration: https://github.com/Gonzalo-Giraldo/crypto-saas/actions/runs/22830521051 / Smoke: https://github.com/Gonzalo-Giraldo/crypto-saas/actions/runs/22830521051 |
| 2026-02-26 | 07:00 | Gonzalo | OK | Verde | OK | No | N/A | Cerrado OK | https://github.com/Gonzalo-Giraldo/crypto-saas/actions/runs/XXXX |

## Criterios rapidos

- `Healthz`:
  - `OK` si `/healthz` responde `{"status":"ok"}`.
- `Smoke Prod`:
  - `Verde` si workflow completo en success.
  - `Rojo` si workflow falla.
- `Auditoria`:
  - `OK` si eventos esperados aparecen y sin errores no explicados.
- `Incidente`:
  - `No` si no hubo afectacion.
  - `Si` si hubo fallo, timeout, error de credenciales, error de deploy, etc.

## Estado final recomendado

- `Cerrado OK`: operacion validada.
- `Cerrado con observacion`: operacion estable con nota de seguimiento.
- `Abierto`: incidente en curso.
| 2026-02-26 | 12:15 | Gonzalo | OK | Verde | OK | No | Limpieza usuarios smoke y validación RBAC | Cerrado OK | https://github.com/Gonzalo-Giraldo/crypto-saas/actions/runs/ID_DEL_RUN |
