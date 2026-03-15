# CHANGE COMMUNICATION LOG

## Micro-modulacion gateway Binance: helper de lectura upstream JSON comun

- Commit: `b2a654b gateway: extract upstream json request helper`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/binance_gateway/main.py`
- Se extrajo un helper privado `_request_upstream_json(method: str, url: str, timeout: int) -> object` para centralizar exclusivamente el tramo comun de lectura upstream JSON: llamada a `_request_upstream(...)`, delegacion de `status_code >= 400` hacia `_raise_upstream_http_error(...)` y `return response.json()`.
- Se actualizaron unicamente 4 endpoints de lectura Binance del gateway: `binance_ticker_24hr`, `binance_klines`, `binance_exchange_info`, `binance_ticker_price`.
- Se preserva la semantica original: timeout efectivo `max(3, REQUEST_TIMEOUT_SECONDS)`, validaciones especificas `invalid_*_payload` fuera del helper, y filtros/armado final de respuesta fuera del helper.
- Validacion posterior al cambio (Docker Python 3.11, subset relacionado): 7 tests ejecutados -> 7 PASS (`test_binance_client_gateway_error_is_sanitized`, `test_binance_client_ticker_price_spot_uses_gateway_row`, `test_binance_client_ticker_price_futures_fallbacks_to_direct`, `test_binance_client_ticker_price_futures_gateway_error_without_fallback_returns_none`, `test_binance_client_exchange_info_spot_uses_gateway_rows`, `test_binance_client_exchange_info_futures_fallbacks_to_direct_single_symbol`, `test_binance_client_exchange_info_futures_gateway_error_without_fallback_raises`).
- Nota de cobertura: no hay prueba directa en este subset para invocacion `GatewayClient(gw.app)` de `/binance/ticker-24hr`, `/binance/klines`, `/binance/exchange-info` y `/binance/ticker-price`.

---

## Micro-modulacion gateway Binance: helper de autorizacion interna + rate-limit preamble

- Commit: `df18236 gateway: extract internal request authorization helper`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/binance_gateway/main.py`
- Se extrajo un helper privado `_authorize_internal_request(x_internal_token: str) -> None` para centralizar exclusivamente el preambulo comun de seguridad en endpoints Binance del gateway.
- Se actualizaron unicamente 6 endpoints Binance (`/binance/test-order`, `/binance/account-status`, `/binance/ticker-24hr`, `/binance/klines`, `/binance/exchange-info`, `/binance/ticker-price`) reemplazando el bloque repetido por el helper.
- Se preserva la semantica original: validacion de token interno con `403/forbidden`, orden auth->rate-limit, y uso de `x_internal_token` como clave de `_enforce_rate_limit(...)`.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 2 tests ejecutados -> 2 PASS (`test_binance_gateway_account_status_uses_spot_base`, `test_binance_gateway_returns_502_on_upstream_unreachable`).
- Nota de cobertura: no hay prueba directa en este subset para los escenarios explicitos `403 forbidden` y `429 rate_limit_exceeded`.

---

## Micro-modulacion ticker-price Binance client: helper gateway/fallback + cobertura SPOT/FUTURES

- Commit: `543c57b client: extract ticker price gateway fallback helper and add coverage`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/worker/app/engine/binance_client.py` y `tests/integration/test_critical_flows.py`
- Se extrajo un helper privado `_fetch_ticker_price_body_with_gateway_fallback(...)` para centralizar exclusivamente el tramo comun de ticker-price: intento por gateway, politica de fallback, fetch direct y obtencion de `body`.
- Se actualizaron unicamente los dos call sites de ticker-price en cliente Binance: `_fetch_symbol_price(...)` (SPOT) y `_fetch_symbol_price_for_market(...)` (FUTURES).
- Se preserva la semantica original SPOT/FUTURES: la construccion de URL/query queda en cada caller; cache/TTL/lock SPOT y regla final `px > 0` permanecen fuera del helper.
- Se añadió cobertura minima directa del flujo ticker-price con 3 tests: `test_binance_client_ticker_price_spot_uses_gateway_row`, `test_binance_client_ticker_price_futures_fallbacks_to_direct`, `test_binance_client_ticker_price_futures_gateway_error_without_fallback_returns_none`.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 4 tests ejecutados -> 4 PASS (`test_binance_client_ticker_price_spot_uses_gateway_row`, `test_binance_client_ticker_price_futures_fallbacks_to_direct`, `test_binance_client_ticker_price_futures_gateway_error_without_fallback_returns_none`, `test_binance_client_gateway_error_is_sanitized`).

---

## Micro-modulacion exchange-info Binance client: helper gateway/fallback + cobertura SPOT/FUTURES

- Commit: `c84aa5a client: extract exchange info gateway fallback helper and add coverage`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/worker/app/engine/binance_client.py` y `tests/integration/test_critical_flows.py`
- Se extrajo un helper privado `_fetch_exchange_info_rows_with_gateway_fallback(...)` para centralizar exclusivamente el tramo comun de exchange-info: intento por gateway, politica de fallback, fetch direct y obtencion de `rows`.
- Se actualizaron unicamente los dos call sites de exchange-info en cliente Binance: `_fetch_exchange_info_symbols(...)` (SPOT) y `_fetch_exchange_info_symbols_for_market(...)` (FUTURES).
- Se preserva la semantica original SPOT/FUTURES: la construccion de URL/query queda en cada caller; cache/TTL/lock SPOT y parseado/filtrado final permanecen fuera del helper.
- Se añadió cobertura minima directa del flujo exchange-info con 3 tests: `test_binance_client_exchange_info_spot_uses_gateway_rows`, `test_binance_client_exchange_info_futures_fallbacks_to_direct_single_symbol`, `test_binance_client_exchange_info_futures_gateway_error_without_fallback_raises`.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 4 tests ejecutados -> 4 PASS (`test_binance_client_exchange_info_spot_uses_gateway_rows`, `test_binance_client_exchange_info_futures_fallbacks_to_direct_single_symbol`, `test_binance_client_exchange_info_futures_gateway_error_without_fallback_raises`, `test_binance_client_gateway_error_is_sanitized`).

---

## Micro-modulacion runtime Binance gateway: helper POST comun + cobertura del path de envio

- Commit: `26f36a4 runtime: extract Binance gateway post helper and add send path coverage`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/worker/app/engine/execution_runtime.py` y `tests/integration/test_critical_flows.py`
- Se extrajo un helper privado `_post_binance_gateway(...)` para centralizar base URL + endpoint, headers con `X-Internal-Token`, `requests.post(...)`, timeout y manejo homogéneo de `status_code >= 400` con `_build_gateway_runtime_error(...)`.
- Se actualizaron unicamente los dos call sites runtime Binance: `_send_binance_test_order_via_gateway(...)` y `_get_binance_account_status_via_gateway(...)`.
- Se preserva la semantica original: `_send_binance_test_order_via_gateway(...)` no parsea JSON en exito; `_get_binance_account_status_via_gateway(...)` mantiene `return response.json()`.
- Se añadió cobertura minima para el path real de envio gateway con `test_binance_runtime_send_path_executes_gateway_chain`.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 4 tests ejecutados -> 4 PASS (`test_binance_runtime_send_path_executes_gateway_chain`, `test_binance_gateway_account_status_uses_spot_base`, `test_binance_gateway_returns_502_on_upstream_unreachable`, `test_binance_runtime_gateway_error_is_sanitized`).

---

## Micro-modulacion del helper MTF trend fields en auto-pick Binance live

- Commit: `8ad5028 modulation: extract auto-pick mtf trend field helper`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/api/app/api/ops.py`
- Se extrajo la funcion anidada `_resolve_trend_fields` fuera de `_auto_pick_from_scan(...)` a un helper privado de modulo `_resolve_auto_pick_mtf_trend_fields(...)`.
- Se hizo explicito `exchange` como parametro del helper y se actualizaron unicamente los dos call sites existentes en `_auto_pick_from_scan(...)`, manteniendo invocacion posicional conservadora.
- Se preserva la semantica de resolucion de trend fields y del fallback MTF para BINANCE cuando faltan campos.
- `_auto_pick_from_scan(...)` se mantiene como orquestador principal del flujo.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 4 tests ejecutados -> 3 PASS, 1 FAIL preexistente (`test_pretrade_auto_pick_dry_run_and_execute`, `tests/integration/test_critical_flows.py:674`).

---

## Micro-modulacion del finalize idempotente best-effort en auto-pick Binance live

- Commit: `6652c94 modulation: extract auto-pick idempotent finalize helper`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/api/app/api/ops.py`
- Se extrajo el bloque de finalizacion idempotente best-effort a un helper privado `_finalize_auto_pick_idempotent_intent_best_effort(...)`.
- El helper encapsula `finalize_idempotent_intent(...)` bajo `try/except Exception: pass`, preservando la semantica best-effort original para ambas ramas.
- El flujo orquestador `_auto_pick_from_scan(...)` conserva el control principal: call al helper con `status_code=500` en la rama de error y con `status_code=200` en la rama de exito; el comentario aclaratorio de la rama de exito se preserva en el call site del caller.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 4 tests ejecutados -> 3 PASS, 1 FAIL preexistente (`test_pretrade_auto_pick_dry_run_and_execute`, `tests/integration/test_critical_flows.py:674`, reproducido contra baseline temporal).

---

## Micro-modulacion de reserva idempotente pre-dispatch en auto-pick Binance live

- Commit: `5cb9297 modulation: extract auto-pick pre-dispatch idempotency helper`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/api/app/api/ops.py`
- Se extrajo la reserva idempotente pre-dispatch a un helper privado `_reserve_auto_pick_pre_dispatch_idempotency(...)`.
- El flujo orquestador `_auto_pick_from_scan(...)` conserva el control principal: `return cached_response` y `idempotency_reserved = True` permanecen en el caller.
- Se preserva el material idempotente y la simetria posterior con `finalize_idempotent_intent(...)` sin cambios funcionales.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 4 tests ejecutados -> 3 PASS, 1 FAIL preexistente (`test_pretrade_auto_pick_dry_run_and_execute`, `tests/integration/test_critical_flows.py:674`, reproducido contra baseline temporal).

---

## Micro-modulacion del semantic intent lock acquire en auto-pick Binance live

- Commit: `621dab3 modulation: extract semantic intent lock acquire helper in auto-pick`
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/api/app/api/ops.py`
- Se extrajo la evaluacion/adquisicion del semantic intent lock a un helper privado `_evaluate_semantic_intent_lock_acquire(...)`.
- El flujo orquestador `_auto_pick_from_scan(...)` conserva el control principal: `log_audit_event(...)`, returns bloqueantes, y ciclo `finally`/unlock de liberacion.
- Se preserva la semantica fail-closed: excepcion durante adquisicion no produce bypass y se trata como no adquisicion.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 4 tests ejecutados -> 3 PASS, 1 FAIL preexistente (`test_pretrade_auto_pick_dry_run_and_execute`, `tests/integration/test_critical_flows.py:674`, reproducido contra baseline temporal).

---

## Micro-modulacion del gate pre-dispatch de ejecucion real en auto-pick Binance live

- Commit: ea9f3a1 modulation: extract real execution pre-dispatch gate helper in auto-pick
- Tipo: micro-modulacion de kernel (sin cambio funcional intencional)
- Scope minimo: `apps/api/app/api/ops.py`
- Se extrajo la evaluacion del gate pre-dispatch de ejecucion real a un helper privado `_evaluate_real_execution_pre_dispatch_gate(...)`.
- El flujo orquestador `_auto_pick_from_scan(...)` se mantiene como orquestador principal y conserva contratos, decisiones bloqueantes y semantica de payloads (`execution: None` vs `execution: {"exit_plan": None}`) sin cambios.
- Validacion posterior al cambio (Docker Python 3.11, subset pertinente): 6 tests ejecutados -> 5 PASS, 1 FAIL preexistente (`test_pretrade_auto_pick_dry_run_and_execute`, `tests/integration/test_critical_flows.py:674`, reproducido tambien contra commit base).

---

## Micro-modulacion del guard broker-side USDT spot en auto-pick Binance live

- Tipo: micro-modulacion de kernel (sin cambio funcional)
- Scope minimo: `apps/api/app/api/ops.py`
- Se extrajo la evaluacion del broker-side USDT spot guard a un helper privado `_evaluate_binance_spot_usdt_broker_guard(...)`.
- El flujo orquestador `_auto_pick_from_scan(...)` conserva contratos, decisiones, razones de bloqueo y payloads de auditoria sin cambios.
- Validacion posterior al cambio (Docker Python 3.11, subset critico): 5/5 PASS
  - `test_binance_gateway_account_status_uses_spot_base`
  - `test_binance_gateway_returns_502_on_upstream_unreachable`
  - `test_binance_runtime_gateway_error_is_sanitized`
  - `test_binance_client_gateway_error_is_sanitized`
  - `test_ibkr_runtime_error_detail_is_sanitized`

---

## Hardening en Binance: sin fallback directo tras rechazo determinístico del gateway

- Commit: 330be57 hardening: avoid Binance direct fallback after deterministic gateway rejection
- En el path Binance con gateway, cuando el gateway ya devuelve un rechazo determinístico del upstream clasificado, el runtime ahora evita el fallback al canal directo y falla en modo cerrado.
- El fallback directo se mantiene para errores de transporte/unreachable.
- La mitigación es acotada: no sustituye idempotency, locks, broker guards ni sanitización general de errores post-dispatch.
- Alcance mínimo: apps/worker/app/engine/execution_runtime.py.

---

## Hardening fail-closed en Binance por estado operativo y permiso MARKET del símbolo

- Commit: e3e418f hardening: fail closed on non-trading or non-market Binance symbols
- En `prepare_binance_market_order_quantity`, usando la metadata ya disponible del símbolo (exchangeInfo), el flujo ahora bloquea en modo fail-closed antes del dispatch si el símbolo no está en estado operativo/trading o si no permite órdenes MARKET.
- Esto evita depender del rechazo posterior del broker/gateway en casos conocidos de antemano para el path Binance.
- La mitigación es puntual: aplica al path Binance, usa metadata ya disponible del símbolo, y no sustituye otras validaciones del exchange ni broker-side guards superiores. Si la metadata no incluye `status`/`contractStatus` u `orderTypes`, la validación no se activa (comportamiento condicionado a disponibilidad de la metadata).
- Alcance mínimo: `apps/worker/app/engine/binance_client.py`.

---

## Hardening fail-closed en Binance para `min_notional` sin precio usable

- Commit: b16cade hardening: fail closed on Binance min_notional without usable price
- En `prepare_binance_market_order_quantity`, si `min_notional > 0` y no hay precio usable para calcular notional, el flujo ahora bloquea en modo fail-closed antes del dispatch.
- Esto evita depender del rechazo posterior del broker en un caso conocido de antemano para el path Binance.
- La mitigación es puntual: no sustituye otras validaciones de filtros del exchange ni broker-side guards superiores.
- Alcance mínimo: `apps/worker/app/engine/binance_client.py`.

---

## Hardening de `order_ref` explícito en path dispatcher IBKR

- Commit: c531ef2 hardening: require explicit order_ref in IBKR dispatcher path
- El path IBKR ahora exige `order_ref` explícito antes del dispatch: `send_ibkr_test_order` falla en modo fail-closed si es invocado sin ese identificador.
- Esto refuerza el contrato del pipeline legítimo del kernel: el flujo válido construye `order_ref` antes del dispatch y ya no depende de que el dispatcher/bridge path lo genere internamente.
- La mitigación es acotada: protege contra llamadas directas no conformes al path IBKR, pero no sustituye idempotency, advisory lock, broker guards ni reconciliación broker vs estado interno.
- Alcance mínimo: `apps/worker/app/engine/execution_runtime.py` y `apps/worker/app/engine/ibkr_client.py`.

---

## Hardening de guard fail-closed en dispatcher Binance por `client_order_id`

- Commit: 034c41e hardening: guard Binance dispatcher against direct calls without client_order_id
- El dispatcher Binance `_send_binance_test_order` ahora falla en modo fail-closed si es invocado sin `client_order_id`.
- Esto refuerza el contrato del pipeline legítimo del kernel: las rutas válidas construyen `client_order_id` antes del dispatch mediante `_build_binance_client_order_id`.
- La mitigación es acotada: protege contra llamadas directas no conformes al dispatcher Binance, pero no sustituye idempotency, advisory lock, broker guards ni reconciliación broker vs estado interno.
- Alcance mínimo: `apps/worker/app/engine/execution_runtime.py`.

---

## Inventario de hardcodes y constantes de dominio/negocio — base de trabajo futura

- Tipo de entrada: análisis documental (sin cambios de código)
- Documento generado: `docs/DOMAIN_CONSTANTS_AUDIT.md`
- Contexto: se completó un análisis de las referencias a quote/funding asset (`USDT`, `BTCUSDT`, `endswith("USDT")`, etc.) y de constantes numéricas de negocio (buffers, multiplicadores, thresholds de scoring/sizing/execution) presentes en el código del sistema.
- Resultado: inventario estructurado en categorías A/B/C/D para tipos textual (T) y numérico (N), separado por contexto Binance / IBKR / Config.
- Los 4 puntos B de consolidación simple ya identificados (T2, T6, T7, N6) serán considerados como grupo de acción futura de bajo riesgo.
- Los puntos C/D requieren revisión de contexto o modelo nuevo; no están planificados todavía.
- **Este inventario NO implica cambio inmediato.** Las acciones se decidirán después, por grupos, en el momento adecuado.

---

## Hardening de guard broker-side USDT spot en Binance auto-pick live

- Commit: a32fb7a hardening: add broker-side USDT spot guard for Binance live auto-pick
- En Binance auto-pick live, antes del dispatch real, se añadió un guard broker-side puntual para SPOT BUY elegible en USDT.
- El guard bloquea fail-closed cuando: estado broker no disponible, `can_trade=false`, `estimated_notional` no usable, `USDT free` no usable o `USDT free < estimated_notional * 1.02`.
- La mitigación es acotada: aplica solo a Binance live SPOT BUY elegible en USDT; no cubre IBKR, futures, SELL, dry-run ni reconciliación general broker vs estado interno.
- Alcance mínimo: `apps/api/app/api/ops.py` y `apps/worker/app/engine/execution_runtime.py`.

---

## Hardening de `client_order_id` determinista en Binance auto-pick live endurecido

- Commit: 5964cac hardening: make Binance client_order_id deterministic for live auto-pick intent
- En el flujo Binance auto-pick live endurecido, cuando existe `intent_key`/`X-Idempotency-Key`, el `client_order_id` ahora se deriva de forma determinista desde material canónico del intento y deja de depender de un componente aleatorio.
- Esto reduce el riesgo de duplicados broker-side en reprocesamientos del mismo intento material dentro de ese flujo, sin cambiar el comportamiento legacy fuera de él.
- La mitigación depende de que exista `intent_key` y no resuelve por sí sola reconciliación broker vs estado interno.
- Alcance mínimo: `apps/worker/app/engine/execution_runtime.py` y paso explícito desde `apps/api/app/api/ops.py` en auto-pick live endurecido.

---

## Hardening de advisory lock semántico en auto-pick live usando conexión dedicada

- Commit: 31176d6 hardening: add dedicated advisory lock connection for live auto-pick intent
- Se reemplazó el uso de `db.execute()` para `pg_try_advisory_lock`/`pg_advisory_unlock` en `_auto_pick_from_scan` por una conexión dedicada explícita (`engine.connect()`), evitando el problema de pool affinity de SQLAlchemy tras `db.commit()` en `reserve_idempotent_intent`.
- Ahora, en el flujo live (`dry_run=false`), la barrera semántica (tenant, usuario, exchange, símbolo, lado) es fiable a través de los commits del ORM Session: acquire y unlock ocurren siempre sobre la misma conexión física.
- El unlock y el cierre de la conexión dedicada ocurren en `finally`, best-effort, sin enmascarar el error principal del flujo.
- Mitigación parcial: aplica solo al flujo live bajo Postgres. En no-Postgres, el comportamiento es conservador/fail-closed (`semantic_intent_lock_requires_postgres`), no equivalente.
- No resuelve race conditions fuera del tramo auto-pick live ni en rutas dry_run.
- Alcance: `apps/api/app/api/ops.py` únicamente. No modifica: `idempotency.py`, `main.py`, `signals.py`, `positions.py`, `trading_controls.py`, `risk_engine.py`.

---

## Hardening de idempotencia pre-dispatch en auto-pick live

- Commit: 0b0e21a hardening: add pre-dispatch idempotency reservation for live auto-pick
- Se implementó una reserva idempotente pre-dispatch en auto-pick live usando la tabla IdempotencyKey.
- Ahora, antes de despachar al broker, se reserva la intención idempotente y se bloquea la ejecución concurrente equivalente.
- La intención se finaliza tanto en éxito como en errores controlados del dispatch, evitando dejar filas in_progress salvo en crash abrupto.
- Mitigación parcial: filas in_progress pueden quedar stale si el proceso se interrumpe inesperadamente.
- No resuelve duplicados a nivel broker si el identificador externo no es determinista.
- Documentación y código alineados; mitigación activa pero no total.

---

## Hardening de execution validation y duplicate prevention en open_from_signal

- Estado:
  - aprobado
  - commits realizados
  - documentación actualizada: sí
  - listo para merge: sí

- Objetivo:
  Reducir dos riesgos operativos relevantes del sistema:
  1. desalineación entre qty validada por exposición y qty final broker-normalized en auto-pick
  2. doble apertura concurrente de posiciones desde la misma señal en open_from_signal

- Riesgo que mitigó:
  - exposición evaluada con qty preliminar en vez de qty final canónica
  - apertura duplicada por carrera concurrente sobre el mismo signal_id
  - trazabilidad insuficiente de requested/sized/normalized qty en auto-pick

- Alcance:
  - archivos tocados:
    - apps/api/app/api/ops.py
    - apps/worker/app/engine/execution_runtime.py
    - apps/api/app/api/positions.py
    - docs/TRADING_RISK_GUARDS.md
    - docs/PRODUCTION_READINESS.md
    - docs/SCHEDULER_AND_CONCURRENCY_MODEL.md
  - superficies NO tocadas:
    - apps/api/app/api/signals.py
    - apps/api/app/main.py
    - apps/api/app/services/risk_engine.py
    - apps/api/app/services/trading_controls.py
    - scheduler redesign
    - reconciliación broker
    - modularización formal del kernel

- Resumen técnico:
  1. Se añadió `resolve_execution_quantity_preview(...)` en execution_runtime.py.
  2. Auto-pick ahora resuelve una qty canónica broker-aware antes del dispatch.
  3. `assert_exposure_limits(...)` en auto-pick usa `normalized_qty` y `price_estimate` del preview canónico.
  4. `selected_qty` quedó alineada con la qty final canónica.
  5. Se añadieron campos de trazabilidad:
     - `selected_qty_requested`
     - `selected_qty_sized`
     - `selected_qty_normalized`
     - `selected_price_estimate`
     - `selected_estimated_notional`
     - `selected_qty_normalization_source`
  6. En `open_from_signal`, la `Signal` se carga con lock transaccional (`with_for_update()`).
  7. Antes de crear posición, se verifica si ya existe una `Position` `OPEN` con el mismo `signal_id`; si existe, se responde `409`.

- Invariantes preservadas:
  - fail-closed
  - idempotencia actual en rutas live
  - paper/live separation
  - auditabilidad
  - tenant isolation
  - sin refactor amplio
  - sin expansión lateral del cambio

- Impacto operativo:
  - auto-pick valida exposición con qty final más cercana a la ejecución real
  - disminuye el riesgo de mismatch entre sizing/exposure/normalización broker
  - `open_from_signal` reduce el riesgo principal de doble apertura concurrente
  - no cambia scheduler
  - no cambia signals.py
  - no resuelve aún por completo duplicados scheduler/manual ni broker idempotency total

- Validación:
  - revisión arquitectónica de diff real en:
    - ops.py
    - execution_runtime.py
    - positions.py
  - verificación semántica de estados:
    - Position: `OPEN` / `CLOSED`
    - Signal: `CREATED`, `EXECUTING`, `OPENED`, `COMPLETED`
  - validación de que `Position.status == "OPEN"` es condición correcta para bloquear duplicados por `signal_id`

- Documentación actualizada:
  - docs/TRADING_RISK_GUARDS.md
  - docs/PRODUCTION_READINESS.md
  - docs/SCHEDULER_AND_CONCURRENCY_MODEL.md

- Commit(s):
  - 0a1be5f hardening: align auto-pick exposure with broker-normalized qty via execution_preview
  - ccae181 hardening: lock signal and prevent duplicate open_from_signal by existing open position

- Sigue abierto:
  - broker order idempotency determinística
  - scheduler vs manual race conditions fuera de open_from_signal
  - duplicate prevention en auto-pick más allá del exposure hardening
  - reconciliación broker centralizada
  - locking más fino en otras superficies

- Siguiente prioridad recomendada:
  Duplicate prevention / execution intent protection en auto-pick o frontera scheduler/manual, con alcance mínimo y sin rediseño grande.

## 041d271 — gateway Binance ticker-price test coverage
- Added two direct gateway tests for `POST /binance/ticker-price`.
- Covered controlled negative scenarios already prioritized for gateway hardening:
  - invalid internal token => `403 forbidden`
  - gateway limiter exceeded => `429 rate_limit_exceeded`
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "ticker_price_forbidden_without_valid_internal_token or ticker_price_rate_limit_exceeded"`
  - Result: `2 passed, 65 deselected`

## 6b85bbf — gateway Binance exchange-info test coverage
- Added two direct gateway tests for `POST /binance/exchange-info`.
- Covered controlled gateway scenarios already prioritized for direct coverage:
  - empty symbols => `400 symbols_required`
  - invalid upstream payload => `502 invalid_exchange_info_payload`
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "exchange_info_symbols_required or exchange_info_invalid_payload"`
  - Result: `2 passed, 67 deselected`

## c6579db — gateway Binance ticker-24hr test coverage
- Added two direct gateway tests for `POST /binance/ticker-24hr`.
- Covered scenarios:
  - invalid upstream payload => `502 invalid_ticker_payload`
  - symbol filtering logic returning envelope `{mode,count,rows}`
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "ticker_24hr_invalid_payload or ticker_24hr_symbol_filtering"`
  - Result: `2 passed, 69 deselected`

## 04ee422 — gateway Binance klines test coverage
- Added two direct gateway tests for `POST /binance/klines`.
- Covered controlled gateway scenarios already prioritized for direct coverage:
  - empty symbol => `400 symbol_required`
  - invalid upstream payload => `502 invalid_klines_payload`
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "klines_symbol_required or klines_invalid_payload"`
  - Result: `2 passed, 71 deselected`

## ade846a — ops ticker gateway envelope contract test coverage
- Added one isolated contract test for the ops Binance ticker helper.
- Covered gateway envelope consumption via `urllib_request.urlopen`.
- Confirmed ops helper reads gateway payload shape `{rows, count, mode}` and extracts `rows` correctly.
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "fetch_binance_ticker_24hr_reads_gateway_envelope"`
  - Result: `1 passed, 73 deselected`

## 9c5554d — ops klines gateway envelope contract test coverage
- Added one isolated contract test for the ops Binance klines helper.
- Covered gateway envelope consumption via `urllib_request.urlopen`.
- Confirmed ops helper reads gateway payload shape `{rows, count, mode}` and returns row arrays correctly.
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "fetch_binance_klines_reads_gateway_envelope"`
  - Result: `1 passed, 74 deselected`

## 27376f6 — binance client ticker-price gateway row envelope contract test coverage
- Added one isolated contract test for Binance client ticker-price helper.
- Covered gateway envelope consumption for payload shape `{row, mode}`.
- Confirmed helper extracts `row.price` and returns float value correctly.
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "binance_client_ticker_price_reads_gateway_row_envelope"`
  - Result: `1 passed, 75 deselected`

## f4d12d4 — binance client exchange-info gateway symbols envelope contract test coverage
- Added one isolated contract test for Binance client exchange-info helper.
- Covered gateway envelope consumption for payload shape `{symbols, count, mode}`.
- Confirmed helper extracts `symbols` and returns per-symbol mapping correctly.
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "binance_client_exchange_info_reads_gateway_symbols_envelope"`
  - Result: `1 passed, 76 deselected`

## dbe5812 — binance client ticker-price gateway failure no-fallback test coverage
- Added one isolated failure-path test for Binance client ticker-price helper.
- Covered behavior when gateway request fails and direct fallback is disabled.
- Confirmed helper returns `None` instead of falling back or raising in this path.
- No production logic changed.
- Validation evidence:
  - `docker compose run --rm api python -m pytest -q tests/integration/test_critical_flows.py -k "ticker_price_gateway_failure_without_direct_fallback_returns_none"`
  - Result: `1 passed, 77 deselected`
