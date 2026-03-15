# Control Cut Log

## 1. Purpose

This log keeps a short, traceable record of formal control cuts.

It is used to:

- capture stop/continue decisions
- preserve context across iterations
- avoid repeating the same risk discussion
- maintain lightweight governance without heavy process

Only add entries for meaningful Level 2/3 checkpoints or when ambiguity justifies a cut.

---

## 2. How To Use

- append new entries at the top
- keep each entry brief and operational
- include evidence and a clear decision
- record next micro-step only (single reversible action)

Do not turn this into a long narrative.

---

## 3. Standard Entry Template

## [CUT-ID] YYYY-MM-DD - Short Title

- Level: 2 or 3
- Trigger: why cut was needed now
- Scope: files/modules/flows in scope
- Risk reviewed: main failure concern
- Evidence checked: tests/logs/manual checks
- Decision: Continue | Continue with condition | Stop
- Condition (if any): concrete guardrail for next step
- Next micro-step: one reversible action
- Owner: name/role

---

## 4. Entries

## 311a2ef — tests: add concurrent same-key auto-pick idempotency coverage

Date: 2026-03-15
Scope:
- tests/integration/test_critical_flows.py

Summary:
Added concurrent same-key characterization coverage for auto-pick live
idempotency behavior using the current integration harness.

Behavior captured:
- two concurrent requests with the same X-Idempotency-Key do not both
  reach live execution
- the test is aligned to the current runtime seam used by live dispatch
- assertions are based on the concurrency invariant rather than on both
  requests returning 200

Validation:
- docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "same_key_concurrent_requests_are_not_both_executed or idempotency_deduplicates_processing or live_http_error"
- Result: 5 passed, 86 deselected, 13 warnings

Classification:
- PASS real
- coverage only
- no production code changes applied in this iteration

## 8fa06ff — tests: add auto-pick live idempotent finalize error-path coverage
- Scope: coverage for live auto-pick idempotent finalize behavior on HTTP error path.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for live auto-pick reserved-idempotency error path
  - Simulated `execute_binance_test_order_for_user(...)` failure with `HTTPException(502, "gateway_upstream_error status=502")`
  - Confirmed business response uses `decision == "insufficient_resources_or_execution_error"`
  - Confirmed there exists a `_finalize_auto_pick_idempotent_intent_best_effort(...)` call with `status_code=500`
  - Confirmed finalize payload preserves `execution.error == "gateway_upstream_error status=502"`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "auto_pick_live_http_error_finalizes_reserved_idempotent_intent"`
- Validation result:
  - PASS real: `1 passed, 88 deselected`
- Notes:
  - The test required three mechanical adjustments to hit the intended branch:
    - neutralize pre-dispatch guards
    - capture all finalize calls instead of only the last one
    - assert existence of the `500` finalize call because the flow may later also emit a `200` finalize

## f35863c — tests: add auto-pick idempotency guard coverage for dry_run vs live
- Scope: policy coverage for auto-pick idempotency guard across dry_run and live execution paths.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_require_idempotency_for_auto_pick_execution(...)`
  - Confirmed `dry_run=False` without `X-Idempotency-Key` raises `HTTPException 400`
  - Confirmed `dry_run=True` without `X-Idempotency-Key` is allowed
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "auto_pick_execution_requires_idempotency_key_only_when_not_dry_run"`
- Validation result:
  - PASS real: `1 passed, 87 deselected`
- Notes:
  - During test insertion, two mechanical adjustments were required:
    - `PretradeAutoPickRequest` is imported from `apps.api.app.schemas.strategy`
    - `_require_idempotency_for_auto_pick_execution(...)` requires keyword arguments

## [CUT-2026-03-14-18] 2026-03-14 - Control de micro-modulacion gateway upstream JSON read helper (commit b2a654b)

- Level: 2
- Trigger: micro-modulacion de kernel en gateway Binance para centralizar el tramo comun de lectura JSON upstream en endpoints de lectura, manteniendo manejo de error upstream sin cambios
- Scope: `apps/binance_gateway/main.py` (extraccion de helper privado `_request_upstream_json(method, url, timeout)` reutilizado por `binance_ticker_24hr`, `binance_klines`, `binance_exchange_info` y `binance_ticker_price`)
- Risk reviewed: posible desviacion semantica en lectura upstream (delegacion de errores via `_raise_upstream_http_error(...)`, preservacion de timeout efectivo `max(3, REQUEST_TIMEOUT_SECONDS)`, y no mover validaciones `invalid_*_payload` ni armado final de respuesta)
- Evidence checked: diff completo revisado; validacion smoke subset relacionado ejecutada (7 tests: `test_binance_client_gateway_error_is_sanitized`, `test_binance_client_ticker_price_spot_uses_gateway_row`, `test_binance_client_ticker_price_futures_fallbacks_to_direct`, `test_binance_client_ticker_price_futures_gateway_error_without_fallback_returns_none`, `test_binance_client_exchange_info_spot_uses_gateway_rows`, `test_binance_client_exchange_info_futures_fallbacks_to_direct_single_symbol`, `test_binance_client_exchange_info_futures_gateway_error_without_fallback_raises` -> 7 PASS)
- Decision: Continue with validation
- Condition (if any): preservar invariantes del contrato gateway (`_raise_upstream_http_error(...)` como unico path de error HTTP upstream, timeout efectivo sin cambios, auth/rate-limit fuera del helper, y validaciones/filtros de negocio en cada endpoint)
- Next micro-step: registrar nota tecnica minima del commit `b2a654b` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-17] 2026-03-14 - Control de micro-modulacion gateway Binance auth/rate-limit preamble (commit df18236)

- Level: 2
- Trigger: micro-modulacion de kernel en gateway Binance para centralizar el preambulo comun de autorizacion interna y rate-limit en endpoints `/binance/*`
- Scope: `apps/binance_gateway/main.py` (extraccion de helper privado `_authorize_internal_request(...)` reutilizado por 6 endpoints Binance: `test-order`, `account-status`, `ticker-24hr`, `klines`, `exchange-info`, `ticker-price`)
- Risk reviewed: posible desviacion semantica en autorizacion/rate-limit (preservacion de `status_code=403`, `detail="forbidden"`, orden auth->rate-limit y clave `x_internal_token`)
- Evidence checked: diff completo revisado; validacion smoke subset pertinente ejecutada (2 tests: `test_binance_gateway_account_status_uses_spot_base`, `test_binance_gateway_returns_502_on_upstream_unreachable` -> 2 PASS)
- Decision: Continue with validation
- Condition (if any): preservar invariantes del contrato gateway (`403/forbidden`, orden auth->rate-limit, clave `x_internal_token`, sin cambios de payload ni logica de negocio en rutas)
- Next micro-step: registrar nota tecnica minima del commit `df18236` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-16] 2026-03-14 - Control de micro-modulacion ticker-price Binance client + cobertura SPOT/FUTURES (commit 543c57b)

- Level: 2
- Trigger: micro-modulacion de kernel en cliente Binance para centralizar el tramo comun gateway/fallback/direct de ticker-price y cerrar brecha de cobertura directa del flujo SPOT/FUTURES
- Scope: `apps/worker/app/engine/binance_client.py` (extraccion de helper privado `_fetch_ticker_price_body_with_gateway_fallback(...)` reutilizado por `_fetch_symbol_price(...)` y `_fetch_symbol_price_for_market(...)`) y `tests/integration/test_critical_flows.py` (3 tests nuevos de ticker-price)
- Risk reviewed: posible desviacion semantica en el flujo ticker-price (politica de fallback, preservacion de timeout gateway calculado y direct timeout=8, preservacion de URL/query por caller, y regla final `px > 0` fuera del helper)
- Evidence checked: diff completo revisado; validacion smoke subset pertinente ejecutada (4 tests: `test_binance_client_ticker_price_spot_uses_gateway_row`, `test_binance_client_ticker_price_futures_fallbacks_to_direct`, `test_binance_client_ticker_price_futures_gateway_error_without_fallback_returns_none`, `test_binance_client_gateway_error_is_sanitized` -> 4 PASS)
- Decision: Continue with validation
- Condition (if any): preservar invariantes del contrato ticker-price (cache/TTL/lock SPOT fuera del helper, URL/query por caller, fallback sin cambios funcionales y regla `px > 0` en callers)
- Next micro-step: registrar nota tecnica minima del commit `543c57b` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-15] 2026-03-14 - Control de micro-modulacion exchange-info Binance client + cobertura SPOT/FUTURES (commit c84aa5a)

- Level: 2
- Trigger: micro-modulacion de kernel en cliente Binance para centralizar el tramo comun gateway/fallback/direct de exchange-info y cerrar brecha de cobertura directa del flujo SPOT/FUTURES
- Scope: `apps/worker/app/engine/binance_client.py` (extraccion de helper privado `_fetch_exchange_info_rows_with_gateway_fallback(...)` reutilizado por `_fetch_exchange_info_symbols(...)` y `_fetch_exchange_info_symbols_for_market(...)`) y `tests/integration/test_critical_flows.py` (3 tests nuevos de exchange-info)
- Risk reviewed: posible desviacion semantica en el flujo exchange-info (politica de fallback, preservacion de URL/query SPOT/FUTURES, propagacion de timeout y preservacion de parseado/caching fuera del helper)
- Evidence checked: diff completo revisado; validacion smoke subset pertinente ejecutada (4 tests: `test_binance_client_exchange_info_spot_uses_gateway_rows`, `test_binance_client_exchange_info_futures_fallbacks_to_direct_single_symbol`, `test_binance_client_exchange_info_futures_gateway_error_without_fallback_raises`, `test_binance_client_gateway_error_is_sanitized` -> 4 PASS)
- Decision: Continue with validation
- Condition (if any): preservar invariantes del contrato exchange-info (URL/query construida por caller, mensaje de error direct sin cambios, cache/TTL/lock SPOT fuera del helper y parseado/filtrado final fuera del helper)
- Next micro-step: registrar nota tecnica minima del commit `c84aa5a` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-14] 2026-03-14 - Control de micro-modulacion runtime Binance gateway + cobertura de send path (commit 26f36a4)

- Level: 2
- Trigger: micro-modulacion de kernel en runtime Binance para eliminar duplicacion del POST a gateway y cerrar brecha de cobertura del path real de envio
- Scope: `apps/worker/app/engine/execution_runtime.py` (helper privado `_post_binance_gateway(...)` reutilizado por `_send_binance_test_order_via_gateway(...)` y `_get_binance_account_status_via_gateway(...)`) y `tests/integration/test_critical_flows.py` (nuevo test `test_binance_runtime_send_path_executes_gateway_chain`)
- Risk reviewed: posible desviacion semantica en el path gateway (headers/token, timeout, formato de error runtime, y parseo JSON solo en account-status)
- Evidence checked: diff completo revisado; validacion smoke subset pertinente ejecutada (4 tests: `test_binance_runtime_send_path_executes_gateway_chain`, `test_binance_gateway_account_status_uses_spot_base`, `test_binance_gateway_returns_502_on_upstream_unreachable`, `test_binance_runtime_gateway_error_is_sanitized` -> 4 PASS)
- Decision: Continue with validation
- Condition (if any): preservar invariantes del contrato runtime (`_send_binance_test_order_via_gateway(...)` sin parseo JSON en exito; `_get_binance_account_status_via_gateway(...)` retornando `response.json()`), manteniendo timeout y sanitizacion de error sin cambios funcionales
- Next micro-step: registrar nota tecnica minima del commit `26f36a4` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-13] 2026-03-14 - Control de micro-modulacion de helper MTF trend fields (commit 8ad5028)

- Level: 2
- Trigger: micro-modulacion de kernel en auto-pick live con extraccion de la funcion anidada de resolucion de trend fields MTF a helper privado de modulo
- Scope: `apps/api/app/api/ops.py` (extraccion de `_resolve_trend_fields` fuera de `_auto_pick_from_scan(...)` como `_resolve_auto_pick_mtf_trend_fields(...)`, con `exchange` como parametro explicito y actualizacion de 2 call sites)
- Risk reviewed: posible desalineacion de resolucion de trend fields (`trend_score`, `trend_1d`, `trend_4h`, `trend_1h`, `micro_trend_15m`), incluyendo fallback MTF para BINANCE cuando faltan campos
- Evidence checked: diff completo revisado; validacion smoke subset de auto-pick live ejecutada (4 tests: 3 PASS, 1 FAIL preexistente `test_pretrade_auto_pick_dry_run_and_execute` en `tests/integration/test_critical_flows.py:674`)
- Decision: Continue with validation
- Condition (if any): mantener invariantes de no cambio semantico (misma logica de calculo/fallback, firma posicional conservadora, y solo 2 call sites actualizados)
- Next micro-step: registrar nota tecnica minima del commit `8ad5028` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-12] 2026-03-14 - Control de micro-modulacion de finalize idempotente best-effort (commit 6652c94)

- Level: 2
- Trigger: micro-modulacion de kernel en auto-pick live con extraccion del bloque de finalizacion idempotente best-effort a helper privado minimo
- Scope: `apps/api/app/api/ops.py` (bloque de finalizacion idempotente en las dos ramas —error (status_code=500) y exito (status_code=200)— dentro de `_auto_pick_from_scan(...)`)
- Risk reviewed: posible perdida de semantica best-effort o de diferenciacion de status_code entre la rama de error y la rama de exito; preservacion del comentario aclaratorio en el call site de exito
- Evidence checked: diff completo revisado; validacion smoke subset de auto-pick live ejecutada (4 tests: 3 PASS, 1 FAIL preexistente `test_pretrade_auto_pick_dry_run_and_execute` en `tests/integration/test_critical_flows.py:674`, reproducido contra baseline temporal)
- Decision: Continue with validation
- Condition (if any): mantener invariantes de finalizacion best-effort (`try/except Exception: pass` dentro del helper) y que el `status_code` correcto sea pasado desde cada call site del caller
- Next micro-step: registrar nota tecnica minima del commit `6652c94` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-11] 2026-03-14 - Control de micro-modulacion de reserva idempotente pre-dispatch (commit 5cb9297)

- Level: 2
- Trigger: micro-modulacion de kernel en auto-pick live con extraccion del bloque de reserva idempotente pre-dispatch a helper privado minimo
- Scope: `apps/api/app/api/ops.py` (reserva idempotente pre-dispatch en `_auto_pick_from_scan(...)`)
- Risk reviewed: posible desalineacion del material idempotente (`endpoint`, `request_payload`) y de la simetria posterior con `finalize_idempotent_intent(...)`
- Evidence checked: diff completo revisado; validacion smoke subset de auto-pick live ejecutada (4 tests: 3 PASS, 1 FAIL preexistente `test_pretrade_auto_pick_dry_run_and_execute` en `tests/integration/test_critical_flows.py:674`, reproducido contra baseline temporal)
- Decision: Continue with validation
- Condition (if any): mantener invariantes idempotentes (material canonico, early return por replay, `idempotency_reserved=True` solo sin replay, y finalize con el mismo payload reservado)
- Next micro-step: registrar nota tecnica minima del commit `5cb9297` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-14-10] 2026-03-14 - Control de micro-modulacion semantic intent lock (commit 621dab3)

- Level: 2
- Trigger: micro-modulacion de kernel en flujo sensible de auto-pick live con extraccion de helper de adquisicion de semantic intent lock
- Scope: `apps/api/app/api/ops.py` (bloque de evaluacion/adquisicion de semantic advisory lock en `_auto_pick_from_scan(...)`)
- Risk reviewed: posible desalineacion semantica en acquire/release del lock (reason codes, fail-closed ante excepcion, preservacion de finally/unlock en caller)
- Evidence checked: diff completo revisado; validacion smoke subset de auto-pick live ejecutada (4 tests: 3 PASS, 1 FAIL preexistente `test_pretrade_auto_pick_dry_run_and_execute` en `tests/integration/test_critical_flows.py:674`, reproducido contra baseline temporal)
- Decision: Continue with validation
- Condition (if any): mantener patron de micro-pasos con diff completo y validacion dirigida antes de siguiente cambio sensible
- Next micro-step: registrar nota tecnica minima del commit `621dab3` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-13-09] 2026-03-13 - Cierre retroactivo de control (commit ea9f3a1)

- Level: 2
- Trigger: micro-modulacion de kernel aplicada antes del cierre final de review completa del diff
- Scope: `apps/api/app/api/ops.py` (extraccion del helper `_evaluate_real_execution_pre_dispatch_gate(...)` en auto-pick Binance live) y trazabilidad metodologica asociada
- Risk reviewed: riesgo procesal por aplicacion de cambio sensible antes del cierre formal de review; riesgo tecnico de desalineacion semantica en el gate pre-dispatch (`real_guard_reason` / `plan_reason`, `enforce_exit_plan`, y payloads bloqueantes)
- Evidence checked: diff completo revisado; verificacion de preservacion de contratos en `_auto_pick_from_scan(...)`; smoke subset pertinente ejecutado (6 tests: 5 PASS, 1 FAIL preexistente `test_pretrade_auto_pick_dry_run_and_execute` en `tests/integration/test_critical_flows.py:674`, reproducido tambien contra el commit base)
- Decision: Retroactive closure accepted
- Condition (if any): incidencia de proceso cerrada retroactivamente; no repetir aplicacion de cambios sensibles antes de diff completo, review final y aprobacion explicita del usuario
- Next micro-step: registrar nota tecnica minima del commit `ea9f3a1` en `docs/CHANGE_COMMUNICATION_LOG.md`
- Owner: engineering/codex session

## [CUT-2026-03-13-08] 2026-03-13 - Cierre retroactivo de validacion dirigida (commit c206c41)

- Level: 2
- Trigger: commit de modulacion realizado antes de completar revision formal final de diff
- Scope: `apps/api/app/api/ops.py` (rama broker-side guard en auto-pick) y trazabilidad metodologica
- Risk reviewed: posible desalineacion semantica del helper extraido y cierre incompleto del proceso de control
- Evidence checked: verificacion dirigida de reason codes, decision `blocked_real_execution_guard`, `top_failed_checks=[broker_guard_reason]`, y payload de auditoria `execution.blocked.broker_spot_guard`
- Decision: Continue with condition
- Condition (if any): no abrir nuevo micro-paso hasta cerrar esta correccion encima con evidencia explicita y decision final
- Next micro-step: cerrar iteracion c206c41 sin cambios de logica de producto
- Owner: engineering/codex session

## [CUT-2026-03-13-07] 2026-03-13 - Entorno habilitado + smoke subset prioritario ejecutado

- Level: 2
- Trigger: execute Priority 1 before any new kernel hardening
- Scope: test runtime enablement and 5 prioritized kernel smoke checks
- Risk reviewed: continuing kernel changes without executable evidence
- Evidence checked: Docker daemon active, Python 3.11 container test run (pytest), manual smoke checks for 5 controls
- Decision: Continue with condition
- Condition (if any): keep kernel changes as single micro-hardening steps with smoke re-run after each change
- Next micro-step: choose one kernel residual (priority-1) and execute one reversible micro-hardening only
- Owner: engineering/codex session

---

## [CUT-2026-03-13-06] 2026-03-13 - Priorización de fases: entorno / kernel / constantes

- Level: 2
- Trigger: need explicit work-phase ordering to avoid dispersion across test environment, kernel hardening, and constants cleanup
- Scope: project priorities and sequencing for next 3 weeks across three work streams (smoke subset, kernel modulación, constants audit)
- Risk reviewed: risk of mixing incompatible work streams simultaneously; risk of deferring critical validation capability
- Evidence checked: CONTROL_CUT_LOG.md (5 prior cuts complete), ENGINEERING_AUDIT_AND_CONTROL_POLICY.md (governance model exists), DOMAIN_CONSTANTS_AUDIT.md (analysis complete, no code changes ready), CHANGE_COMMUNICATION_LOG.md (8 hardenings documented, residuals mapped)
- Decision: Continue with explicit phase ordering
- Conditions:
  1. Phase 1 (Prioridad 1): Entorno de pruebas / smoke subset — COMIENCE INMEDIATAMENTE. Blocker para fases 2 y 3. Acción: fix Python 3.11 environment (local OR Docker), ejecutar 5 smoke checks prioritarios, documentar en SMOKE_VALIDATION_RESULTS.md. Timeline: 1-2 horas
  2. Phase 2 (Prioridad 2): Modulación del kernel — COMIENCE DESPUÉS QUE SMOKE ESTÉ VALIDADA. Continuidad lógica post-consolidación S3. Acción: 1 micro-hardening que cierre residual prioridad-1 (duplicado broker-side, error asymmetry, o partial exchange coverage). Timeline: 3-5 horas post-smoke
  3. Phase 3 (Prioridad 3): Limpieza / constantes — BACKLOG CONTROLADO. Postergado a 1-2 semanas post-kernel. Acción: arquitectura decide sobre puntos C/D (no ready today), ejecutar Grupo B (simple) solo si arquitectura aprueba post-kernel. Timeline: decision + grouped execution post-kernel
- Ordering rationale: Phase 1 is pure blocker (no validation capability without tests). Phase 2 follows logically (consolidation S3 done, residuals mapped, microhardening pattern proven). Phase 3 is orthogonal (analysis complete, points C/D not ready for code, can wait 2 weeks without context loss)
- What NOT to mix: (a) do not mix smoke + kernel changes in parallel; (b) do not mix kernel + constants changes simultaneously; (c) do not treat constants{B,C,D} as single phase (are separate groups with different readiness levels)
- Next micro-step: execute Phase 1 immediately (restore Python 3.11 test runtime and run smoke subset)
- Owner: engineering/codex session

---

## [CUT-2026-03-13-05] 2026-03-13 - Entorno de pruebas + smoke subset prioritario (habilitacion)

- Level: 2
- Trigger: need executable evidence before any new kernel hardening
- Scope: test environment readiness and prioritized kernel smoke subset execution capability
- Risk reviewed: inability to validate hardened behavior due runtime/tooling blockers
- Evidence checked: local venv dependency install, pytest startup error under Python 3.9, container-based fallback attempt blocked by Docker daemon not running
- Decision: Continue with condition
- Condition (if any): no new kernel hardening until Python 3.11-capable test run is available and smoke subset is executed
- Next micro-step: fix runtime layer first (use Python 3.11 interpreter or enable Docker daemon), then run prioritized smoke checks in order
- Owner: engineering/codex session

## [CUT-2026-03-13-04] 2026-03-13 - Consolidacion Kernel S3 (smoke evidence check)

- Level: 2
- Trigger: need minimal executable evidence before deciding whether to resume kernel hardening
- Scope: kernel hardenings and related tests/docs evidence across test_critical_flows and operational docs
- Risk reviewed: insufficient executable confirmation vs documented hardenings; first-line residuals still open
- Evidence checked: existing targeted tests for gateway/bridge error sanitization and idempotency behavior; docs risk/limitations sections
- Decision: Continue with condition
- Condition (if any): do not add new kernel hardening until targeted smoke checks run in a ready test environment
- Next micro-step: restore test environment dependencies (FastAPI/pytest stack) and run prioritized smoke subset before selecting one next kernel action
- Owner: engineering/codex session

## [CUT-2026-03-13-03] 2026-03-13 - Consolidacion Kernel S2 (operational validation)

- Level: 2
- Trigger: need to validate whether current kernel hardenings are sufficiently settled before adding new hardening
- Scope: evidence and residual-risk ordering across CHANGE_COMMUNICATION_LOG.md, TRADING_RISK_GUARDS.md, and PRODUCTION_READINESS.md
- Risk reviewed: first-line residuals still open (duplicate risk outside hardened lane, post-dispatch error asymmetry, partial exchange-filter coverage)
- Evidence checked: controls implemented list, explicit limitations, and remaining-risks sections in technical docs
- Decision: Continue with condition
- Condition (if any): pause new kernel hardening now; run targeted smoke/evidence check and residual map ordering first
- Next micro-step: execute Consolidation Kernel S3 focused on targeted smoke checks and one ranked recommendation for next action
- Owner: engineering/codex session

## [CUT-2026-03-13-02] 2026-03-13 - Kernel Control Cut #1 (phase checkpoint)

- Level: 2
- Trigger: cumulative kernel hardenings completed; need go/no-go decision for immediate further hardening vs consolidation
- Scope: kernel execution safeguards and post-dispatch behavior documented in CHANGE_COMMUNICATION_LOG.md, TRADING_RISK_GUARDS.md, and PRODUCTION_READINESS.md
- Risk reviewed: residual first-line kernel risks (broker-side duplicate prevention outside hardened flow, partial exchange-filter coverage, error-sanitization asymmetry, dry-run idempotency gap)
- Evidence checked: hardened controls list and residual-risk sections in TRADING_RISK_GUARDS.md and PRODUCTION_READINESS.md, plus latest hardening entries in CHANGE_COMMUNICATION_LOG.md
- Decision: Continue with condition
- Condition (if any): do not open broad redesign; execute one micro-hardening at a time only if it closes a first-line kernel risk with minimal reversible scope
- Next micro-step: pause coding and run short consolidation pass (targeted smoke/evidence review + residual-risk ordering), then decide next single kernel micro-hardening or phase shift
- Owner: engineering/codex session

## [CUT-2026-03-13-01] 2026-03-13 - Binance post-dispatch fallback control

- Level: 2
- Trigger: residual ambiguity after gateway deterministic rejection in Binance dispatch path
- Scope: runtime dispatch fallback behavior in apps/worker/app/engine/execution_runtime.py
- Risk reviewed: second direct dispatch attempt after deterministic upstream rejection
- Evidence checked: runtime error path review, gateway error classification (`gateway_upstream_error status=... code=...`), post-dispatch flow audit in ops
- Decision: Continue with condition
- Condition (if any): allow gateway->direct fallback only for transport/unreachable failures; fail-closed when deterministic gateway rejection is already classified
- Next micro-step: apply minimal guard in `_send_binance_test_order` and re-check no unrelated behavior changes
- Owner: engineering/codex session

## 041d271 — tests: add gateway ticker-price coverage for 403 and 429 scenarios
- Scope: direct gateway test coverage only.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added direct `GatewayClient(gw.app)` coverage for `POST /binance/ticker-price`
  - Covered explicit gateway responses:
    - `403 forbidden` for invalid internal token
    - `429 rate_limit_exceeded` after limiter threshold
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "ticker_price_forbidden_without_valid_internal_token or ticker_price_rate_limit_exceeded"`
- Validation result:
  - PASS real: `2 passed, 65 deselected`
- Notes:
  - Local `pytest` binary was unavailable (`code 127`), so equivalent containerized validation was used.

## 6b85bbf — tests: add gateway exchange-info coverage for 400 and 502 scenarios
- Scope: direct gateway test coverage only.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added direct `GatewayClient(gw.app)` coverage for `POST /binance/exchange-info`
  - Covered explicit gateway responses:
    - `400 symbols_required`
    - `502 invalid_exchange_info_payload`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "exchange_info_symbols_required or exchange_info_invalid_payload"`
- Validation result:
  - PASS real: `2 passed, 67 deselected`

## c6579db — tests: add gateway ticker-24hr coverage and validate response envelope contract
- Scope: direct gateway test coverage only.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added direct `GatewayClient(gw.app)` coverage for `POST /binance/ticker-24hr`
  - Covered explicit gateway scenarios:
    - `502 invalid_ticker_payload`
    - symbol filtering behaviour
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "ticker_24hr_invalid_payload or ticker_24hr_symbol_filtering"`
- Validation result:
  - PASS real: `2 passed, 69 deselected`
- Notes:
  - Endpoint returns an envelope structure `{mode, count, rows}` rather than a raw list.

## 04ee422 — tests: add gateway klines coverage for 400 and 502 scenarios
- Scope: direct gateway test coverage only.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added direct `GatewayClient(gw.app)` coverage for `POST /binance/klines`
  - Covered explicit gateway responses:
    - `400 symbol_required`
    - `502 invalid_klines_payload`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "klines_symbol_required or klines_invalid_payload"`
- Validation result:
  - PASS real: `2 passed, 71 deselected`

## ade846a — tests: add ops ticker gateway envelope contract coverage
- Scope: contract coverage between gateway response and ops helper consumption.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for ops ticker helper consuming gateway envelope via `urllib_request.urlopen`
  - Validated extraction of `rows` from gateway payload shape `{rows, count, mode}`
  - Final helper under test is module-level `_fetch_binance_ticker_rows`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "fetch_binance_ticker_24hr_reads_gateway_envelope"`
- Validation result:
  - PASS real: `1 passed, 73 deselected`
- Notes:
  - Initial hypothesis used `_fetch_binance_ticker_24hr`, but local audit confirmed the module-level helper name is `_fetch_binance_ticker_rows`.

## 9c5554d — tests: add ops klines gateway envelope contract coverage
- Scope: contract coverage between gateway response and ops helper consumption.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for ops klines helper consuming gateway envelope via `urllib_request.urlopen`
  - Validated extraction of row arrays from gateway payload shape `{rows, count, mode}`
  - Verified expected request payload `{symbol, interval, limit}`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "fetch_binance_klines_reads_gateway_envelope"`
- Validation result:
  - PASS real: `1 passed, 74 deselected`

## 27376f6 — tests: add binance client ticker-price gateway row envelope contract coverage
- Scope: contract coverage between gateway response and binance client helper consumption.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for Binance client ticker-price helper consuming gateway envelope
  - Validated extraction of `row` from gateway payload shape `{row, mode}`
  - Verified `_fetch_symbol_price("BTCUSDT")` returns `50000.0`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "binance_client_ticker_price_reads_gateway_row_envelope"`
- Validation result:
  - PASS real: `1 passed, 75 deselected`

## f4d12d4 — tests: add binance client exchange-info gateway symbols envelope contract coverage
- Scope: contract coverage between gateway response and binance client helper consumption.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for Binance client exchange-info helper consuming gateway envelope
  - Validated extraction of `symbols` from gateway payload shape `{symbols, count, mode}`
  - Verified returned mapping contains `BTCUSDT` with expected filter payload
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "binance_client_exchange_info_reads_gateway_symbols_envelope"`
- Validation result:
  - PASS real: `1 passed, 76 deselected`

## dbe5812 — tests: add binance client ticker-price gateway failure no-fallback coverage
- Scope: contract/policy coverage for Binance client ticker-price helper when gateway fails and direct fallback is disabled.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_fetch_symbol_price("BTCUSDT")`
  - Simulated `_post_gateway(...)` failure with `gateway_upstream_error status=502`
  - Confirmed helper returns `None` when `BINANCE_GATEWAY_FALLBACK_DIRECT=false`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "ticker_price_gateway_failure_without_direct_fallback_returns_none"`
- Validation result:
  - PASS real: `1 passed, 77 deselected`

## 81dcf4f — tests: add binance client exchange-info gateway failure no-fallback coverage
- Scope: contract/policy coverage for Binance client exchange-info helper when gateway fails and direct fallback is disabled.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_fetch_exchange_info_symbols(["BTCUSDT"])`
  - Simulated `_post_gateway(...)` failure with `gateway_upstream_error status=502`
  - Confirmed helper propagates the `RuntimeError` when `BINANCE_GATEWAY_FALLBACK_DIRECT=false`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "exchange_info_gateway_failure_without_direct_fallback_raises"`
- Validation result:
  - PASS real: `1 passed, 78 deselected`

## 37bca4a — tests: add binance client ticker-price gateway failure with direct fallback coverage
- Scope: contract/policy coverage for Binance client ticker-price helper when gateway fails and direct fallback is enabled.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_fetch_symbol_price("BTCUSDT")`
  - Simulated `_post_gateway(...)` failure with `gateway_upstream_error status=502`
  - Confirmed helper falls back to direct `requests.get(...)` path when `BINANCE_GATEWAY_FALLBACK_DIRECT=true`
  - Verified returned direct price is `50123.45`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "ticker_price_gateway_failure_with_direct_fallback_returns_direct_price"`
- Validation result:
  - PASS real: `1 passed, 79 deselected`

## 5624817 — tests: add binance client exchange-info gateway failure with direct fallback coverage
- Scope: contract/policy coverage for Binance client exchange-info helper when gateway fails and direct fallback is enabled.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_fetch_exchange_info_symbols(["BTCUSDT"])`
  - Simulated `_post_gateway(...)` failure with `gateway_upstream_error status=502`
  - Confirmed helper falls back to direct `requests.get(...)` path when `BINANCE_GATEWAY_FALLBACK_DIRECT=true`
  - Verified returned mapping contains `BTCUSDT` with valid `filters`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "exchange_info_gateway_failure_with_direct_fallback_returns_direct_symbols"`
- Validation result:
  - PASS real: `1 passed, 80 deselected`

## 6a6a96e — tests: add binance runtime strict-mode fallback policy coverage
- Scope: policy coverage for Binance runtime strict mode gateway configuration.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_assert_binance_gateway_policy()`
  - Validated strict mode rejection when gateway is enabled and `BINANCE_GATEWAY_FALLBACK_DIRECT=true`
  - Confirmed raised `HTTPException` uses status `500` and strict-mode policy detail
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "strict_mode_rejects_direct_fallback_enabled"`
- Validation result:
  - PASS real: `1 passed, 81 deselected`

## db00a39 — tests: add binance runtime account-status gateway fallback coverage
- Scope: runtime fallback coverage for Binance account-status when gateway fails and direct fallback is enabled.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_get_binance_account_status(...)`
  - Simulated `_get_binance_account_status_via_gateway(...)` failure with `gateway_upstream_error status=502`
  - Confirmed runtime falls back to direct `get_account_status(...)` path when `BINANCE_GATEWAY_FALLBACK_DIRECT=true`
  - Verified returned payload preserves `canTrade` and `balances`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "account_status_gateway_failure_with_direct_fallback_returns_direct_payload"`
- Validation result:
  - PASS real: `1 passed, 82 deselected`

## 12a2cd3 — tests: add binance runtime send-test-order upstream error policy coverage
- Scope: runtime policy coverage for Binance send-test-order when gateway returns a sanitized upstream error.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_send_binance_test_order(...)`
  - Simulated `_send_binance_test_order_via_gateway(...)` failure with `gateway_upstream_error status=502`
  - Confirmed runtime relaunches the sanitized gateway error even when `BINANCE_GATEWAY_FALLBACK_DIRECT=true`
  - Confirmed runtime does not fall back to direct `send_test_order(...)` in this path
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "send_test_order_gateway_upstream_error_does_not_fallback_direct"`
- Validation result:
  - PASS real: `1 passed, 83 deselected`

## 8b317c5 — tests: add binance runtime send-test-order unsanitized fallback coverage
- Scope: runtime fallback coverage for Binance send-test-order when gateway fails with an unsanitized error and direct fallback is enabled.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `_send_binance_test_order(...)`
  - Simulated `_send_binance_test_order_via_gateway(...)` failure with unsanitized error `temporary network failure`
  - Confirmed runtime falls back to direct `send_test_order(...)` when `BINANCE_GATEWAY_FALLBACK_DIRECT=true`
  - Verified direct fallback receives the expected forwarded arguments
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "send_test_order_unsanitized_gateway_error_uses_direct_fallback"`
- Validation result:
  - PASS real: `1 passed, 84 deselected`

## d531017 — tests: add binance runtime account-status entrypoint error mapping coverage
- Scope: runtime entrypoint error-mapping coverage for Binance account status.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `get_binance_account_status_for_user(...)`
  - Simulated internal `_get_binance_account_status(...)` failure with `gateway_upstream_error status=502`
  - Confirmed runtime maps the internal failure to `HTTPException` with status `502`
  - Verified the returned detail is `Binance account status failed: gateway_upstream_error status=502`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "account_status_entrypoint_maps_internal_failure_to_http_502"`
- Validation result:
  - PASS real: `1 passed, 85 deselected`

## 4384915 — tests: add binance runtime test-order entrypoint error mapping coverage
- Scope: runtime entrypoint error-mapping coverage for Binance test-order flow.
- File changed: `tests/integration/test_critical_flows.py`
- Evidence:
  - Added isolated test for `execute_binance_test_order_for_user(...)`
  - Simulated internal `_send_binance_test_order_with_retry(...)` failure with `gateway_upstream_error status=502`
  - Confirmed runtime maps the internal failure to `HTTPException` with status `502`
  - Verified the returned detail is `Binance test order failed: gateway_upstream_error status=502`
- Validation executed:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "test_order_entrypoint_maps_internal_failure_to_http_502"`
- Validation result:
  - PASS real: `1 passed, 86 deselected`


## Policy clarification — auto-pick idempotent finalize semantics

Decision taken during idempotency/concurrency audit.

Observation:
Auto-pick live execution path may emit two finalize calls for the same
reserved idempotent intent:

    finalize(status_code=500)   # error path
    finalize(status_code=200)   # later closure path

This creates a semantic inconsistency risk where a failed execution may
later appear finalized as success depending on idempotency storage
overwrite behavior.

Policy decision:
A reserved idempotent intent MUST be finalized exactly once.

Operational rule:
- If finalize(status_code=500) occurs, that finalize is terminal.
- The execution flow MUST NOT emit a later finalize(status_code=200)
  for the same idempotent intent.

Status:
policy pending implementation.

Scope:
apps/api/app/api/ops.py auto-pick live execution path.

Rationale:
Preserve idempotency semantics and prevent success-overwrite of error
finalization.

Deferred follow-up (not in this iteration):
- Evaluate stable client_order_id propagation toward broker/exchange.
- Evaluate post-error reconciliation against broker/exchange status.


## c359b25 — fix: prevent double finalize for reserved auto-pick idempotent intent

Date: 2026-03-15
Scope:
- apps/api/app/api/ops.py
- tests/integration/test_critical_flows.py

Summary:
Applied a minimal control-flow fix so a reserved auto-pick idempotent
intent is finalized at most once within the same request flow.

Behavior captured:
- error-path finalize(status_code=500) now marks the reserved intent as
  already finalized
- later success-path finalize(status_code=200) is skipped when that
  earlier error finalize already occurred

Validation:
- docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "double_finalize or live_http_error"
- Result: 2 passed, 88 deselected

Classification:
- PASS real
- behavior aligned with prior policy clarification
- coverage targeted only; no broader runtime validation performed


## Coverage note — auto-pick idempotency dedup test is sequential, not real concurrency

Date: 2026-03-15
Scope:
- tests/integration/test_critical_flows.py
- tests/integration/conftest.py
- apps/api/app/api/ops.py
- docs/SCHEDULER_AND_CONCURRENCY_MODEL.md

Observation:
The current auto-pick idempotency deduplication test validates repeated
same-key behavior through sequential requests, not through simultaneous
concurrent requests.

Evidence:
- Existing dedup test performs two sequential requests with the same
  idempotency key and asserts response deduplication / single execution.
- No concurrency primitives are present in the current integration test
  harness (no threading, concurrent.futures, asyncio.gather, Barrier,
  Lock, Semaphore, or equivalent patterns).
- Runtime documentation continues to describe partial mitigation for real
  concurrency through advisory lock semantics plus pre-dispatch
  idempotent reservation.

Classification:
- PASS real for sequential same-key deduplication
- Coverage gap for real concurrent same-key race validation
- No code or test harness changes applied in this iteration


## Risk note — theoretical race window between semantic lock and idempotent reservation

Date: 2026-03-15
Scope:
- apps/api/app/api/ops.py
- docs/SCHEDULER_AND_CONCURRENCY_MODEL.md

Observation:
A theoretical race window may exist between semantic advisory-lock
acquisition and durable pre-dispatch idempotent reservation for
auto-pick live execution.

Meaning:
One protection layer limits overlapping execution intent, while the
second protection layer records the reserved idempotent intent. If those
two protections are not observed as one atomic state transition, a small
theoretical interval may exist where another actor cannot yet observe
the reserved intent.

Current status:
- theoretical risk only
- not reproduced in this iteration
- no concurrent race test added in this iteration
- no production code changes applied for this note

Classification:
- policy pending
- coverage gap remains for real concurrent same-key validation


## Backlog note — local extraction candidate for binance auto-pick live flow

Date: 2026-03-15
Scope:
- apps/api/app/api/ops.py

Observation:
After several idempotency/concurrency hardening iterations, the Binance
auto-pick live path appears functionally safer but still structurally
distributed across multiple inline responsibilities inside ops.py.

Responsibilities currently intermixed:
- live policy / guard evaluation
- idempotency lifecycle handling
- live dispatch / execution
- finalize/store result behavior

Architectural opportunity:
A future local extraction may improve readability, seam clarity, and
testability by grouping the live auto-pick pipeline into a single
internal flow unit without changing product behavior.

Current status:
- maintainability/testability note only
- no bug classified from this observation
- no refactor applied in this iteration

Classification:
- backlog candidate
- non-urgent
- policy neutral
