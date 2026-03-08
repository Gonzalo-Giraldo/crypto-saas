# Documento Tecnico Maestro y Plan Modular

Fecha: 2026-03-08
Proyecto: crypto-saas (FastAPI + PostgreSQL + Render)

## 1) Objetivo

Este documento consolida el estado tecnico actual del aplicativo, su operacion completa end-to-end y una descomposicion por modulos para analisis iterativo y toma de decisiones de cambio/adicion bajo las definiciones de diseno vigentes.

Fuentes base de diseno:
- docs/backend_definition_of_done.md
- docs/04_runbook_validacion.md
- docs/frontend_mvp_blueprint.md

## 2) Alcance funcional actual (codigo real)

El backend implementa:
- Identidad y acceso: JWT access/refresh, revocacion por token y por sesion, 2FA TOTP, enforcement opcional de 2FA y password age.
- Usuarios y gobierno: CRUD operativo de usuarios, roles, cambio de credenciales, reset 2FA admin, readiness check por usuario y agregado.
- Riesgo y trading control: kill-switch global, limites de exposicion por simbolo/exchange, perfiles de riesgo dinamicos.
- Flujo operativo de trading: signals -> claim -> open position -> close position.
- Ejecucion operativa: pretrade/exit checks, scan, auto-pick, auto-exit, test-orders y account-status para BINANCE/IBKR.
- Seguridad operativa: secretos cifrados en reposo, postura de seguridad, rotacion de llaves.
- Observabilidad funcional: auditoria, export firmado/hash, dashboard y console web.
- Learning pipeline: snapshots de decision, labeling, retention, rollup horario.

## 3) Arquitectura logica actual

### 3.1 API principal
- Entrada HTTP: `apps/api/app/main.py`
- Routers:
  - `/auth` -> `apps/api/app/routes/auth.py`
  - `/users` -> `apps/api/app/api/users.py`
  - `/signals` -> `apps/api/app/api/signals.py`
  - `/positions` -> `apps/api/app/api/positions.py`
  - `/ops` -> `apps/api/app/api/ops.py`

### 3.2 Capas internas
- `api/*`: contrato HTTP + autorizacion por dependencia.
- `services/*`: logica reutilizable (riesgo, crypto, idempotencia, assignments, runtime policy).
- `models/*`: modelo persistente SQLAlchemy.
- `schemas/*`: contratos de entrada/salida Pydantic.

### 3.3 Ejecucion externa
- Runtime de ejecucion: `apps/worker/app/engine/execution_runtime.py`.
- Gateway BINANCE: `apps/binance_gateway/main.py`.

### 3.4 Scheduler interno API
- `main.py` inicia hilo opcional (`AUTO_PICK_INTERNAL_SCHEDULER_ENABLED`) que ejecuta:
  - market-monitor tick,
  - auto-pick tick,
  - learning pipeline,
  - auto-exit tick (si habilitado).

## 4) Modelo de datos operativo (resumen)

Entidades nucleares:
- Seguridad/identidad: `users`, `user_two_factor`, `revoked_token`, `session_revocation`.
- Operacion: `signals`, `positions`, `daily_risk_state`, `runtime_settings`, `audit_log`.
- Integracion brokers: `exchange_secret`, `strategy_assignment`, `strategy_runtime_policy`.
- Riesgo dinamico: `risk_profile_config`, `user_risk_profile_override`, `user_risk_settings`.
- Idempotencia: `idempotency_keys`.
- Learning: `learning_decision_snapshot`, `learning_decision_outcome`, `learning_rollup_hourly`, `market_trend_snapshot`.

## 5) Seguridad actual implementada

Controles existentes:
- JWT con `typ`, `jti`, `iat`, `tid` y validacion de tenant en dependencia de usuario actual.
- Revocacion puntual (logout) y global por usuario (`revoke-all` + corte por `revoked_after`).
- 2FA TOTP por usuario y enforcement configurable para admins/emails.
- Password age policy configurable.
- Cifrado en reposo de secretos de exchange (Fernet derivado de `ENCRYPTION_KEY`).
- RBAC (`admin`, `operator`, `viewer`, `trader`, `disabled`) y guardrails de ultimo admin.
- Auditoria de acciones criticas y export verificable.

## 6) Operacion end-to-end (flujo)

1. Login admin/trader con OTP cuando aplica.
2. Configuracion de secretos de exchange (si exchange habilitado por assignment).
3. Pretrade checks por exchange/estrategia.
4. Scan/auto-pick (manual o tick admin/scheduler).
5. Ejecucion test-order (modo seguro) y account-status.
6. Apertura/cierre de posicion en flujo `signals/positions` con reglas de riesgo.
7. Auto-exit por reglas de salida, cool-down y politicas internas.
8. Learning pipeline etiqueta resultados y genera rollups.
9. Operacion y control desde `/ops/dashboard` y `/ops/console`.

## 7) Hallazgos tecnicos relevantes (estado 2026-03-08)

### 7.1 Alto
- Gateway BINANCE: referencia a `BINANCE_BASE` no definida en `account-status`.
  - Archivo: `apps/binance_gateway/main.py` (ruta account-status).
  - Impacto: endpoint de estado de cuenta en gateway puede fallar en runtime.

### 7.2 Alto
- Scripts operativos vacios: `scripts/backup_db.sh`, `scripts/restore_db.sh`.
  - Impacto: continuidad operativa/DR incompleta.

### 7.3 Medio
- Stubs vacios en worker: `apps/worker/app/celery_app.py`, `apps/worker/app/db/session.py`.
  - Impacto: confusion arquitectonica (worker formal vs runtime embebido en API).

### 7.4 Medio
- Archivos `.save` en codigo fuente (`main.py.save`, `auth.py.save`).
  - Impacto: riesgo de drift/carga accidental.

### 7.5 Medio (mitigado localmente)
- Riesgo de overflow/memoria en rollup learning por ventanas largas.
  - Se aplico hardening local: limite por filas y agregacion mas controlada.
  - Requiere deploy para impacto efectivo en Render.

## 8) Definiciones de diseno para decisiones de cambio

Criterios obligatorios (DoD + runbook + blueprint):
- Seguridad primero: no degradar controles de auth, 2FA, cifrado, auditoria.
- Operacion sin SQL manual para tareas normales.
- Trazabilidad completa de acciones criticas.
- Cambios compatibles con runbooks existentes.
- Riesgo controlado en ejecucion: kill-switch, exposure limits, idempotencia.
- Enfoque conservador para flujos reales (real trading guardrails).

## 9) Descomposicion modular propuesta

### Modulo M1: Identidad, Sesion y RBAC
Incluye:
- `/auth/*`, `api/deps.py`, `core/security.py`, modelos `user`, `revoked_token`, `session_revocation`, `user_two_factor`.
Objetivo de revision:
- robustez de autenticacion, expiracion y revocacion, politica de roles y tenant.

### Modulo M2: Usuarios y Gobierno Operativo
Incluye:
- `/users/*`, readiness individual/agregado, lifecycle de usuario.
Objetivo:
- garantizar onboarding/admin sin brechas ni operaciones manuales.

### Modulo M3: Secretos y Criptografia
Incluye:
- `exchange_secrets.py`, `crypto.py`, `key_rotation.py`, endpoints de secretos y postura.
Objetivo:
- confidencialidad, rotacion segura, higiene de secretos.

### Modulo M4: Riesgo, Controles y Exposicion
Incluye:
- `risk_profiles.py`, `trading_controls.py`, partes de `positions.py` y `ops.py`.
Objetivo:
- consistencia de limites, kill-switch, y bloqueo preventivo.

### Modulo M5: Signals y Positions (Core de trading interno)
Incluye:
- `signals.py`, `positions.py`, `daily_risk_state`.
Objetivo:
- invariantes de estados y consistencia de PnL/riesgo.

### Modulo M6: Pretrade/Scan/Auto-pick
Incluye:
- bloques de `ops.py` para check, scan, auto-pick, strategy/runtime policy.
Objetivo:
- calidad de seleccion, trazabilidad y controles de ejecucion.

### Modulo M7: Auto-exit y Politicas de cierre
Incluye:
- `run_exit_tick_for_tenant`, checks de salida y cierre interno.
Objetivo:
- seguridad de cierre automatizado y limites por tick.

### Modulo M8: Learning Pipeline
Incluye:
- snapshots, label, retention, rollup, reportes learning.
Objetivo:
- estabilidad de procesamiento, costo/memoria, utilidad operativa del modelo.

### Modulo M9: Integraciones Broker y Gateway
Incluye:
- `execution_runtime.py`, `binance_client.py`, `ibkr_client.py`, `apps/binance_gateway`.
Objetivo:
- resiliencia de integracion, retries, fallback, manejo de errores.

### Modulo M10: Observabilidad, Auditoria y Consolas
Incluye:
- `/ops/dashboard*`, `/ops/console`, `/ops/audit*`, export, snapshot diario.
Objetivo:
- visibilidad operativa accionable y evidencia para decision.

### Modulo M11: Plataforma, Deploy y Operacion Continua
Incluye:
- `Dockerfile`, `docker-compose.yml`, workflows GitHub, scripts operativos.
Objetivo:
- reproducibilidad, smoke/validacion, remediacion y continuidad.

## 9.1) Frontera Backend/Frontend por modulo

- Backend puro: M1, M2, M3, M4, M5, M6, M7, M8, M9.
- Mixto (backend + frontend embebido): M10.
- DevOps/operacion continua: M11.
- Frontend separado: actualmente no existe app web independiente; la UI operativa vive en `apps/api/app/api/ops.py` (`/ops/dashboard`, `/ops/console`).

## 10) Metodo de analisis por modulo (iterativo)

Para cada modulo se ejecuta el mismo marco:
1. Inventario tecnico (archivos/endpoints/modelos).
2. Invariantes y contratos (que no se puede romper).
3. Hallazgos (severidad P1/P2/P3).
4. Opciones de cambio (A/B/C con trade-offs).
5. Decision acordada (aceptar, posponer, descartar).
6. Plan de implementacion (small batches + rollback).
7. Validacion (tests, smoke, runbook).

## 11) Orden recomendado de analisis

1. M1 Identidad, Sesion y RBAC
2. M3 Secretos y Criptografia
3. M4 Riesgo, Controles y Exposicion
4. M6 Pretrade/Auto-pick
5. M7 Auto-exit
6. M8 Learning
7. M9 Integraciones Broker/Gateway
8. M2 Usuarios/Gobierno
9. M10 Observabilidad
10. M11 Plataforma/Deploy
11. M5 Signals/Positions (cierre de invariantes core)

Razon del orden:
- primero seguridad y controles transversales,
- luego decision engines,
- despues integraciones y operacion.

## 12) Decisiones iniciales sugeridas (pre-analisis detallado)

- D1: Corregir bug `BINANCE_BASE` en gateway antes de escalar pruebas de account-status.
- D2: Implementar backup/restore reales o retirar scripts vacios del flujo operativo.
- D3: Desplegar hardening de rollup learning a Render y monitorear `processed_rows/truncated`.
- D4: Definir oficialmente si el worker formal existe o si la ejecucion queda embebida en API.

## 13) Proximo paso

Iniciar analisis detallado por modulo en el orden propuesto, comenzando por M1.
