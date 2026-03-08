---
name: "Tech Debt Warnings v2"
about: "Seguimiento de limpieza tecnica post-release"
title: "[Tech Debt Warnings v2] Cleanup backlog"
labels: ["tech-debt", "post-release", "backend"]
assignees: []
---

## Objetivo
Reducir deuda tecnica y warnings de runtime/test sin afectar comportamiento funcional.

## Alcance
- Pydantic v2 migration:
  - reemplazar config de clase legacy por `ConfigDict`.
- Cliente de pruebas:
  - migrar uso de shortcut `app=` hacia `transport=WSGITransport/ASGITransport` segun corresponda.
- FastAPI lifecycle:
  - mantener `lifespan` y retirar remanentes legacy si aparecen.

## Criterios de cierre
- Warnings deprecados reducidos de forma medible en `Integration Tests`.
- Sin regresiones funcionales en workflows:
  - `Integration Tests` verde.
  - `Smoke Prod` verde.
- Documentacion actualizada con cambios de compatibilidad.

## Plan sugerido
1. Inventario de warnings por fuente.
2. Corregir en lotes pequenos (1 fuente por commit).
3. Validar en CI por cada lote.
4. Cerrar issue con evidencia (links de runs verdes).
