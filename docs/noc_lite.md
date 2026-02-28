# NOC-Lite Operacion Diaria

Guia de decision rapida para operar con minima intervencion humana.

## 1) Panel unico a revisar

- Dashboard: `GET /ops/dashboard` (UI)
- Fuente JSON: `GET /ops/dashboard/summary?real_only=true`
- Workflows:
  - `Dual Ops Daily`
  - `Security Posture Daily`
  - `Quarterly Rotation` (cuando aplique ventana)

## 2) Semaforo y accion

### Verde

Condicion:
- `overall_status=green`
- `users_missing_2fa=0`
- `users_with_stale_secrets=0`
- `Dual Ops Daily` y `Security Posture Daily` en verde.

Accion:
- Sin intervencion humana.
- Registrar observacion corta: "Operacion normal".

### Amarillo

Condicion (cualquiera):
- `overall_status=yellow`
- `blocked_open_attempts_total > 0`
- aumento puntual de errores sin tendencia de 2 dias.

Accion:
- Revisar `Tail log` de workflows.
- Verificar filtros de dashboard (`real_only`, `exchange`, `email`).
- Si no hay impacto operativo, mantener monitoreo.
- Si se repite 2 dias, escalar a incidente preventivo.

### Rojo

Condicion (cualquiera):
- `overall_status=red`
- `users_missing_2fa > 0`
- `users_with_stale_secrets > 0`
- workflow en rojo.

Accion:
- Abrir/usar incidente (boton `Open Incident` en dashboard o issue existente).
- Aplicar runbook:
  - credenciales/2FA/secretos,
  - reintento controlado,
  - rollback si es ventana de rotacion.
- Cerrar incidente solo con evidencia de recuperacion (workflow verde).

## 3) Regla preventiva automatizada

Esta automatizada en `Security Posture Daily`:
- si `errors_total` sube 2 dias consecutivos (`trends_7d`) => falla workflow e incidente preventivo.
- si ademas `pretrade_blocked_last_24h > 0` => tratar como prioridad alta.

## 4) Umbrales operativos recomendados

- 2FA faltante: tolerancia `0`.
- Secretos vencidos: tolerancia `0`.
- Bloqueos de apertura (`blocked_open_attempts_total`):
  - `0`: normal
  - `1-2`: observacion
  - `>=3`: revisar reglas de entrada y riesgo.
- Errores:
  - estable o descendente: normal/observacion.
  - ascendente 2 dias: incidente preventivo.

## 5) Evidencia minima diaria

- `Security Posture Daily` artifact:
  - `security_posture_output.log`
  - `security_dashboard_snapshot.json`
- `Dual Ops Daily` artifact:
  - `dual_ops_output.log`
- Estado final:
  - `Cerrado OK`
  - `Cerrado con observacion`
  - `Abierto` (incidente en curso)

## 6) Modo de actuacion recomendado

- Operacion normal: automatica.
- Intervencion humana: solo cuando hay rojo o regla preventiva disparada.
- Cambios sensibles (rotacion): usar `Quarterly Rotation` con rollback habilitado.
