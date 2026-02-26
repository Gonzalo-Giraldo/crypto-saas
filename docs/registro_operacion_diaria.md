# Registro Operacion Diaria - Crypto SaaS

Uso:
- Completar una fila por dia.
- Adjuntar link del run de GitHub Actions (Smoke Prod).
- Si hubo incidente, agregar resumen corto y estado final.

## Tabla diaria

| Fecha | Hora | Operador | Healthz | Smoke Prod | Auditoria | Incidente | Accion aplicada | Estado final | Link run |
|---|---|---|---|---|---|---|---|---|---|
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

