# Revision Modular Iterativa

Fecha inicio: 2026-03-08
Base de referencia: docs/05_documento_tecnico_modular.md

## Cierre de release
- Fecha cierre: 2026-03-08
- Estado final: M1..M11 cerrados (analizado/decidido/implementado = SI).
- Validacion final:
  - Integration Tests: verde.
  - Smoke Prod: verde.
- Commits de consolidacion (main):
  - `2364e56` (M10/M11 base)
  - `9bc4248` (M1..M9 + docs tecnicas)
  - `a9ce107` (fix integration + smoke fallback)
  - `58aa0d1` (fix TOTP smoke)

## Estado general
- Modulos definidos: M1..M11
- Frontend separado: NO (UI embebida en backend via `ops.py`)
- Metodo: hallazgos P1/P2/P3 + decision propuesta por modulo

## Matriz de propiedad por modulo
- M1 Identidad/Sesion/RBAC: Backend
- M2 Usuarios y Gobierno: Backend
- M3 Secretos y Criptografia: Backend
- M4 Riesgo/Controles/Exposicion: Backend
- M5 Signals/Positions: Backend
- M6 Pretrade/Scan/Auto-pick: Backend
- M7 Auto-exit: Backend
- M8 Learning pipeline: Backend
- M9 Integraciones Broker/Gateway: Backend
- M10 Observabilidad/Console/Dashboard: Mixto (backend + frontend embebido)
- M11 Plataforma/Deploy/Operacion continua: DevOps + Backend operativo

## M1 - Identidad, Sesion y RBAC

### Hallazgos
- [P1] `POST /auth/register` abierto para alta publica en entorno operativo.
- [P2] Politica de password no uniforme entre register/reset.
- [P2] Comparacion de revocacion con manejo de timezone mejorable.
- [P3] Sin rate-limit de login a nivel app.

### Decision propuesta
- Cerrar registro publico por flag de produccion + endurecer password policy + normalizar UTC en revocacion.

### Acciones implementadas
- Se agrego flag `AUTH_PUBLIC_REGISTER_ENABLED` (default `false`) y se bloquea `/auth/register` cuando esta deshabilitado.
- Se implemento politica unificada de password (`validate_password_policy`) y se aplica en `register` y `PUT /users/{id}/password`.
- Se corrigio comparacion de revocacion con conversion explicita a UTC en `auth` y `deps`.
- Se agrego rate-limit basico de login en memoria con controles por usuario/IP y ventana configurable.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M2 - Usuarios y Gobierno Operativo

### Hallazgos
- [P2] Flujo robusto en admin, pero sin workflow formal de aprobacion para cambios sensibles (rol/email/password).
- [P3] Readiness duplicado en `/users` y `/ops` (riesgo de drift funcional).

### Decision propuesta
- Mantener endpoints actuales.
- Agregar regla de doble confirmacion para acciones criticas en UI y unificar readiness en una sola funcion compartida.

### Acciones implementadas
- Readiness unificado en servicio compartido `services/user_readiness.py` y reutilizado por `/users/readiness/report` y `/ops/admin/readiness/daily-gate`.
- Se exige `reason` minimo para cambios sensibles:
  - `PATCH /users/{id}/role`
  - `PATCH /users/{id}/email`
  - `PUT /users/{id}/password`
  - `POST /users/{id}/2fa/reset` (query `reason`).
- Se agrega `reason` al `audit_log` en esos cambios.
- Alta admin de usuario (`POST /users`) ahora aplica politica de password y normaliza email a lowercase.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M3 - Secretos y Criptografia

### Hallazgos
- [P2] Cifrado en reposo correcto, pero falta versionado de llave/cifrado para rotaciones futuras escalables.
- [P2] `reencrypt` funciona, pero no hay modo "canary" por lote ni rollback explicito documentado.

### Decision propuesta
- Introducir `key_version` en `exchange_secret` + rotacion por lotes con checkpoints.

### Acciones implementadas
- Se agrega `key_version` en `exchange_secret` (default `v1`) con compatibilidad hacia atras.
- Cifrado ahora escribe con version activa (`ENCRYPTION_KEY_VERSION`) y descifrado intenta version declarada + fallback seguro (`ENCRYPTION_KEY_PREVIOUS*`).
- Rotacion de secretos endurecida:
  - soporte `new_version`,
  - `batch_size`,
  - `canary_count`,
  - contador de `failed`.
- Endpoint `/ops/security/reencrypt-exchange-secrets` actualizado para estos parametros y auditoria ampliada.
- Guardrail para Binance en runtime:
  - `BINANCE_GATEWAY_STRICT_MODE=true` obliga gateway habilitado y `BINANCE_GATEWAY_FALLBACK_DIRECT=false`.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M4 - Riesgo, Controles y Exposicion

### Hallazgos
- [P2] Buen baseline (kill-switch, exposure, profiles), pero faltan limites por horario/sesion centralizados.
- [P2] Controles repartidos entre `positions.py` y `ops.py` (riesgo de divergencia).

### Decision propuesta
- Consolidar motor de reglas de riesgo en servicio unico reutilizable y declarativo.

### Acciones implementadas
- Hardening de entradas en riesgo/exposicion:
  - `assert_exposure_limits` ahora rechaza `qty/price_estimate` no numericos, no finitos, negativos o fuera de rango.
  - Nuevos limites configurables: `RISK_INPUT_MAX_QTY`, `RISK_INPUT_MAX_PRICE`.
- Hardening de esquemas de estrategia:
  - validacion de numeros finitos en `PretradeCheckRequest`,
  - `qty` acotado y campos sensibles no negativos,
  - limite de tamaño para `candidates` en scan/auto-pick (max 500),
  - validaciones de precios y tiempo de apertura (`opened_minutes`) en `ExitCheckRequest`,
  - limite configurable adicional: `RISK_INPUT_MAX_OPENED_MINUTES`.
- Gobernanza del kill-switch:
  - al deshabilitar trading en `/ops/admin/trading-control`, ahora exige `reason` con minimo 8 caracteres.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M5 - Signals y Positions

### Hallazgos
- [P2] Flujo base estable, pero orientado a LONG en varios caminos historicos.
- [P3] Falta trazabilidad de transicion de estados como maquina de estados explicita.

### Decision propuesta
- Definir state-machine formal (`Signal`, `Position`) y validadores de transicion.

### Acciones implementadas
- Maquina de estados formal para `Signal` y `Position` en servicio dedicado:
  - `apps/api/app/services/state_machine.py`
  - transiciones validadas con errores `409` para cambios invalidos.
- Hardening de `SignalCreate`:
  - normalizacion/validacion de `symbol` y `module`,
  - validacion numerica finita en campos de riesgo/precio,
  - regla estructural LONG: `stop_loss < entry_price < take_profit`.
- Hardening operacional:
  - `POST /signals/claim` ahora valida `limit` en rango `[1, 100]`,
  - `POST /positions/close` valida `exit_price` y `fees` finitos y en rango.
- Idempotencia en cierre de posicion:
  - soporte de `X-Idempotency-Key` en `POST /positions/close`.
- Pruebas de integracion M5 agregadas:
  - limites de `claim`,
  - estructura invalida de precios en señal,
  - guardas de `exit_price` no finito,
  - replay idempotente en cierre.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M6 - Pretrade/Scan/Auto-pick

### Hallazgos
- [P2] Lógica potente pero extensa en un solo archivo (`ops.py`), mantenibilidad baja.
- [P2] Complejidad alta de scoring/guardrails; requiere particion por subdominios.

### Decision propuesta
- Extraer a modulo `decision_engine` (checks, scoring, pick, audit payload builders).

### Acciones implementadas
- Hardening operacional en pretrade:
  - `check/scan/auto-pick` ahora valida `_assert_exchange_enabled` para BINANCE/IBKR.
- Idempotencia extendida:
  - `POST /ops/execution/pretrade/{exchange}/scan` ahora soporta `X-Idempotency-Key`.
  - `POST /ops/execution/pretrade/{exchange}/auto-pick` ahora soporta `X-Idempotency-Key`.
- Extraccion inicial de motor de decision:
  - nuevo modulo `apps/api/app/services/decision_engine.py` con utilidades de ranking y umbral por lado.
  - `ops.py` reutiliza esas utilidades en `scan` y `auto-pick`.
- Pruebas de integracion M6 agregadas:
  - replay/conflicto idempotente en scan,
  - deduplicacion idempotente en auto-pick,
  - bloqueo cuando exchange esta deshabilitado para usuario.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M7 - Auto-exit

### Hallazgos
- [P2] Buenas protecciones por tick (pause, cooldown, max closes/errors).
- [P2] Algoritmo largo y denso en `ops.py`, difícil de testear en granularidad fina.

### Decision propuesta
- Separar `exit_policy_engine` y `exit_executor` con pruebas unitarias por regla.

### Acciones implementadas
- Extraccion inicial del motor de politica:
  - nuevo modulo `apps/api/app/services/exit_policy_engine.py` con:
    - ordenamiento de candidatos de salida,
    - resolucion base de `policy_skip_reason` (`max_errors`, `paused`, `max_closes`, `symbol_cooldown_tick`).
- Hardening en endpoint admin:
  - `POST /ops/admin/exit/tick` ahora soporta `X-Idempotency-Key`.
  - se evita reprocesamiento de tick con mismo payload/clave idempotente.
- Integracion en `ops.py`:
  - el loop de auto-exit usa utilidades del `exit_policy_engine`.
  - comportamiento funcional se mantiene (sin cambios de reglas de negocio).
- Pruebas de integracion M7 agregadas:
  - deduplicacion idempotente del tick admin,
  - politica `paused`,
  - politica `max_closes_per_tick`.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M8 - Learning Pipeline

### Hallazgos
- [P1] Riesgo de presión de memoria ya detectado en rollup para ventanas largas (mitigado localmente; pendiente deploy).
- [P2] Falta control explícito de calidad de datos de entrada/salida del labeling.

### Decision propuesta
- Desplegar hardening de rollup a producción y añadir métricas de calidad de labeling.

### Acciones implementadas
- Metricas de calidad de learning:
  - `POST /ops/admin/learning/label` ahora reporta tasas: `labeled_rate_pct`, `expired_rate_pct`, `no_price_rate_pct`.
  - `GET /ops/admin/learning/status` ahora reporta tasas: `pending_rate_pct`, `labeled_rate_pct`, `expired_rate_pct`, `no_price_rate_pct`.
- Validacion estricta de parametros/filtros admin:
  - rangos controlados para `hours`, `limit`, `horizon_minutes` con respuesta `400` en valores invalidos.
  - validacion de `exchange` (`ALL|BINANCE|IBKR`) y `outcome_status` (`ALL|PENDING|LABELED|EXPIRED|NO_PRICE`).
- Extraccion inicial de utilidades:
  - nuevo modulo `apps/api/app/services/learning_pipeline_engine.py` para validaciones y calculo de tasas.
- Pruebas de integracion M8 agregadas:
  - presencia de metricas de calidad en status,
  - rechazo de rangos invalidos,
  - rechazo de filtros invalidos.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M9 - Integraciones Broker y Gateway

### Hallazgos
- [P1] Bug en gateway BINANCE: referencia `BINANCE_BASE` no definida en account-status.
- [P2] Estrategia de fallback/directo existe, pero falta contrato de errores homogéneo entre runtime y gateway.

### Decision propuesta
- Corregir bug crítico de variable + estandarizar errores/retries por adaptador.

### Acciones implementadas
- Fix critico en Binance gateway:
  - `apps/binance_gateway/main.py` corrige `/binance/account-status` para usar `BINANCE_SPOT_BASE` (elimina referencia invalida a `BINANCE_BASE`).
- Hardening de errores en gateway:
  - manejo uniforme de upstream unreachable (`502 binance_upstream_unreachable`),
  - errores HTTP upstream normalizados (`binance_upstream_error status=... code=...`).
- Estandarizacion de contrato de error en runtime/cliente:
  - `apps/worker/app/engine/execution_runtime.py` y `apps/worker/app/engine/binance_client.py` ahora normalizan errores de gateway a formato corto y sin payload sensible.
- Homologacion IBKR:
  - `apps/worker/app/engine/ibkr_client.py` ahora normaliza errores bridge a `ibkr_upstream_error status=... code=...` y desconexion a `ibkr_upstream_unreachable`.
  - `apps/worker/app/engine/execution_runtime.py` ahora sanea errores IBKR de salida publica (`ibkr_*` o `ibkr_runtime_error`), evitando exposicion de detalles sensibles.
- Pruebas de integracion M9 agregadas:
  - account-status usa base spot correcta en gateway,
  - gateway responde `502` en desconexion upstream,
  - runtime y cliente Binance no filtran secretos en errores.
  - cliente/runtime IBKR con contrato de error normalizado y sin fuga de secretos.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M10 - Observabilidad, Auditoria y Consolas

### Tipo
- Mixto: backend + frontend embebido en `ops.py` (`/ops/dashboard`, `/ops/console`).

### Funcionalidad actual
- Consola operativa servida por backend en dos rutas (`/ops/dashboard`, `/ops/console`).
- Flujo UI consolidado en 3 pantallas:
  - ingreso (`email`, `password`, `otp/token` o token directo),
  - menú principal por módulos,
  - pantalla de detalle por módulo con botón de regreso al menú.
- Salida de sesión centralizada desde menú principal (`Salir`).

### Propuesta
- Mantener arquitectura mixta en esta fase, pero mover la UI de consola a template dedicado:
  - nuevo template `apps/api/app/templates/ops_console_v2.html`,
  - `ops.py` renderiza template en lugar de mantener HTML/JS inline largo.
- Priorizar legibilidad operativa:
  - navegación simple tipo “login -> menú -> módulo -> volver a menú”,
  - menor ruido visual y menor duplicidad de bloques de información.

### Por qué
- Reduce acoplamiento de `ops.py` (API vs vista), mejorando mantenibilidad.
- Facilita pruebas de smoke sobre estructura UI sin romper endpoints.
- Disminuye riesgo de errores por cambios manuales repetidos en HTML inline extenso.

### Ventajas
- Operación más clara para humano (flujo lineal y reversible).
- Menor superficie de persistencia de sesión en navegador (token en `sessionStorage`).
- Base lista para evolución futura (extraer frontend separado si el alcance crece).

### Acciones implementadas
- Se añadió renderer de templates en `ops.py` (`_render_ops_template`).
- `/ops/dashboard` y `/ops/console` ahora sirven `ops_console_v2.html`.
- Se implementó template con:
  - pantalla 1: autenticación,
  - pantalla 2: menú por módulos,
  - pantalla 3: vista de módulo con `Volver al menu`,
  - logout desde menú.
- Pruebas M10 actualizadas:
  - `test_ops_console_page_served` valida shell de 3 pantallas.
  - `test_ops_dashboard_page_serves_same_console_shell` valida paridad en `/ops/dashboard`.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## M11 - Plataforma, Deploy y Operacion Continua

### Tipo
- DevOps + Backend operativo.

### Funcionalidad actual
- Operacion continua ya activa con smoke, remediacion Render y jobs diarios/semanales en GitHub Actions.
- Runbooks operativos existentes para validacion y produccion.
- Riesgo original: backup/restore DB no ejecutables y presencia de artefactos `.save`.

### Propuesta
- Implementar `scripts/backup_db.sh` y `scripts/restore_db.sh` con guardrails operativos.
- Agregar runbook DR especifico para backup/restore.
- Endurecer higiene de release:
  - excluir `*.save` en git,
  - control CI para fallar si aparecen `.save`,
  - limpieza de archivos `.save` existentes.

### Por qué
- Sin backup/restore ejecutable no hay recuperacion verificable ante incidente de datos.
- Restore sin confirmacion explicita aumenta riesgo de error humano critico.
- Archivos legacy `.save` elevan riesgo de drift y confusiones en despliegue/auditoria.

### Ventajas
- Continuidad operativa real (backup/restore repetible y validable).
- Menor probabilidad de restauraciones accidentales.
- Mejor disciplina de repositorio y pipeline (bloqueo preventivo de artefactos legacy).

### Acciones implementadas
- `scripts/backup_db.sh` implementado con:
  - `DRY_RUN`,
  - formato `custom|plain`,
  - compresion opcional para SQL plano,
  - checksum `.sha256`,
  - cifrado opcional (`openssl`) y retencion (`KEEP_LAST`).
- `scripts/restore_db.sh` implementado con:
  - `DRY_RUN`,
  - confirmacion obligatoria `CONFIRM_RESTORE=YES` para ejecucion real,
  - verificacion de checksum,
  - soporte `.dump`, `.sql`, `.sql.gz` y variantes cifradas `.enc`.
- Nuevo runbook:
  - `docs/runbook_disaster_recovery.md`.
- CI hardening:
  - `.github/workflows/integration-tests.yml` falla si detecta archivos `*.save`.
- Higiene repo:
  - `.gitignore` ahora incluye `*.save`.
- Limpieza:
  - eliminados `apps/api/app/routes/auth.py.save` y `apps/api/app/main.py.save`.

### Estado
- Analizado: SI
- Decidido: SI (aprobado por usuario)
- Implementado: SI

---

## Secuencia de revision conjunta propuesta
1. M1
2. M9
3. M11
4. M3
5. M4
6. M6
7. M7
8. M8
9. M2
10. M10
11. M5

Razon:
- prioriza seguridad e incidentes criticos de integracion/plataforma,
- luego robustez de motor operativo,
- finalmente consolidacion funcional y UX.

## Regla de trabajo para cada modulo (cuando lo revisemos juntos)
1. Confirmar alcance y frontera backend/frontend.
2. Elegir decision (aceptar, modificar, posponer).
3. Aplicar cambios en lote pequeño.
4. Validar con pruebas/runbook.
5. Cerrar modulo con checklist.
