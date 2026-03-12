TRADING_RISK_GUARDS.md
# TRADING_RISK_GUARDS.md

## Modelo de defensas del motor de trading

Este documento describe las **defensas operativas y de riesgo** que protegen el sistema de trading.

No propone cambios.  
Describe **el comportamiento actual observado en el sistema**.

Este documento complementa:

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/TRADING_ENGINE.md`
- `docs/RISK_MODEL.md`
- `docs/SIZING_MODEL.md`
- `docs/TRADING_DECISION_MODEL.md`

Su objetivo es explicar:

- qué defensas existen
- dónde se aplican
- qué riesgos mitigan
- qué fragilidades siguen presentes

---

# 1. Filosofía general de protección

El sistema sigue una filosofía de defensa por capas.

Principios principales:

- fallar cerrado ante incertidumbre
- validar antes de ejecutar
- no asumir que el broker siempre responde bien
- proteger paper/live como frontera crítica
- evitar órdenes duplicadas
- mantener separación por tenant, usuario y cuenta
- preservar trazabilidad y auditabilidad

Estas defensas se aplican antes, durante y después de la decisión de trading.

---

# 2. Tipos principales de guardas

Las defensas del sistema se agrupan en estas categorías:

1. guardas de tenant y autenticación
2. guardas de señal y transición de estado
3. guardas de exposición
4. guardas de sizing
5. guardas de idempotencia
6. guardas de paper vs live
7. guardas de scheduler y concurrencia
8. guardas de broker execution
9. guardas de reconciliación y consistencia

---

# 3. Guardas de tenant y autenticación

El sistema usa un modelo híbrido de tenant.

Defensas clave:

- tenant raíz en `users.tenant_id`
- claim `tid` en JWT
- validación estricta de:
  
```text
token.tid == user.tenant_id

fail-closed si hay mismatch

kill-switch por tenant:

trading_enabled:{tenant_id}

Riesgo mitigado:

fuga de datos entre tenants

ejecución en tenant equivocado

scheduler ejecutando con contexto incorrecto

Archivos clave:

apps/api/app/api/deps.py

apps/api/app/routes/auth.py

apps/api/app/main.py

apps/api/app/services/trading_controls.py

4. Guardas de señal y transición de estado

Las señales son un punto crítico de entrada.

Defensas observadas:

validación de señal antes de ejecución

flujo controlado de claim

validación de estado antes de apertura de posición

transición esperada de estados de señal

separación entre intake, selección y apertura

Endpoints críticos:

POST /signals

GET /signals

POST /signals/claim

POST /positions/open_from_signal

Riesgo mitigado:

doble procesamiento de una señal

ejecución de una señal ya usada

apertura de posición desde estado inválido

Hardening reciente:

- `open_from_signal` en `apps/api/app/api/positions.py` ahora bloquea transaccionalmente la fila de `Signal` (`SELECT ... FOR UPDATE`) antes de validaciones y apertura.
- en `apps/api/app/api/positions.py` se verifica la existencia de una `Position` con `signal_id` y `status == OPEN` antes de crear una posición adicional.

Archivo clave:

apps/api/app/api/signals.py

apps/api/app/api/positions.py

5. Guardas de exposición

La exposición se valida mediante:

assert_exposure_limits(...)

Archivo:

apps/api/app/services/trading_controls.py

Valida:

cantidad abierta por símbolo

notional abierto por exchange

cantidad de posiciones abiertas

límites máximos configurados
Hardening reciente:

- en el pipeline auto-pick, la validación final de exposición usa `normalized_qty` calculada para el broker via `execution_preview` (Binance normaliza, IBKR passthrough). 
- el payload de auto-pick ahora expone `selected_qty_requested`, `selected_qty_sized`, `selected_qty_normalized`, `selected_price_estimate`, `selected_estimated_notional`, `selected_qty_normalization_source` en respuesta/auditoría.
Se usa en:

pretrade checks

scans

auto-pick

open_from_signal

Riesgo mitigado:

sobreexposición por símbolo

exceso de posiciones abiertas

crecimiento de riesgo no controlado

Limitación actual:

La exposición se basa principalmente en estado interno (Position), no en balance vivo del broker.

6. Guardas de sizing

El sizing actual está protegido indirectamente por varias capas:

validación de qty de entrada

clasificación de liquidez

reducción por SELL

validación de exposición

normalización por broker

Funciones clave:

_classify_liquidity_state(...)

_auto_pick_from_scan(...)

prepare_binance_market_order_quantity(...)

Riesgo mitigado:

órdenes demasiado grandes

ejecución en mala liquidez

violación de reglas mínimas del broker

Fragilidad actual:

reglas hardcoded (0.35, 0.5, 1.0, 0.0)

separación parcial entre qty validada y qty ejecutada

7. Guardas de idempotencia

La idempotencia es una defensa crítica del sistema.

Mecanismos observados:

uso de IdempotencyKey

X-Idempotency-Key obligatorio cuando dry_run=false

caching/consumo de respuesta idempotente en endpoints relevantes

protección en auto-pick live

auditoría de respuestas

Archivo y funciones relacionadas:

apps/api/app/api/ops.py

modelo IdempotencyKey

Riesgo mitigado:

órdenes duplicadas

repeticiones por retries

reenvío accidental de requests

Limitación actual:

no todas las rutas dry_run parecen exigir idempotency key

el broker puede seguir viendo reintentos como nuevas órdenes si el identificador final no es estable

8. Guardas de paper vs live

El sistema protege la frontera entre paper y live mediante:

flag dry_run

X-Idempotency-Key para live

AUTO_PICK_REAL_GUARD_ENABLED

allowlists por email, exchange y símbolo

exit-plan guard

evidencia de auditoría con modo de ejecución

Regla principal:

dry_run = true

es el estado más conservador.

Riesgo mitigado:

envío accidental de orden real

mezcla de balances paper/live

mezcla de posiciones paper/live

relajación del control operacional

Fragilidad futura:

Si en el futuro se añade una ruta real nueva, debe repetir todas estas protecciones.

9. Guardas de scheduler y concurrencia

El scheduler corre embebido en la API.

Defensas actuales:

ejecución por tenant

advisory lock por tenant

separación de loops por tenant

diseño orientado a idempotencia

control de re-entrada parcial

Archivo principal:

apps/api/app/main.py

Riesgo mitigado:

doble tick simultáneo por tenant

ejecución solapada entre réplicas

duplicación de auto-pick

Fragilidad actual:

la protección depende del lock por tenant

algunas rutas manuales y del scheduler pueden competir por el mismo estado

no toda concurrencia parece resuelta con locking transaccional fino

10. Guardas de ejecución contra broker

La capa de broker execution usa adaptadores específicos.

Archivos clave:

apps/worker/app/engine/execution_runtime.py

apps/worker/app/engine/binance_client.py

apps/worker/app/engine/ibkr_client.py

Defensas observadas:

separación por broker

normalización de cantidad

manejo específico por adaptador

retries controlados

uso de test orders

logging de resultados

Riesgo mitigado:

errores por precision

incompatibilidad entre brokers

ordenes inválidas

Fragilidad actual:

Binance usa client_order_id no completamente determinista

IBKR puede entrar por bridge o fallback simulado

el comportamiento del broker no se usa como fuente única de verdad

11. Guardas de reconciliación y consistencia

La arquitectura asume que el estado del sistema puede diferir del broker.

Defensas actuales:

audit logging

separación entre decisión, ejecución y apertura de posición

uso de posición interna como base de exposición

consulta opcional de estado de cuenta en broker

Riesgo mitigado:

pérdida total de trazabilidad

decisiones sin contexto histórico

errores invisibles al operador

Fragilidad actual:

no hay reconciliación fuerte y centralizada en estos módulos

balances reales del broker no forman parte principal del sizing

posiciones internas pueden divergir del broker si no se reconcilia bien

12. Riesgos que estas guardas sí contienen bien

Las defensas actuales contienen razonablemente bien:

separación tenant básica

separación paper/live

validaciones pretrade

exposición simple

prevención parcial de duplicados

ejecución test por broker

scheduler multi-tenant con lock

13. Riesgos que siguen abiertos

Los riesgos más sensibles que siguen abiertos son:

duplicación de órdenes a nivel broker

race conditions entre scheduler y acciones manuales

desalineación entre exposure check y qty final

dependencia de reglas hardcoded en sizing

ausencia de balance real del broker en la decisión

reconciliación incompleta entre estado interno y broker

posibilidad de doble apertura desde la misma señal bajo concurrencia

14. Archivos más sensibles para estas defensas

Los módulos más sensibles del sistema siguen siendo:

apps/api/app/api/ops.py

apps/api/app/main.py

apps/api/app/api/deps.py

apps/api/app/routes/auth.py

apps/api/app/services/trading_controls.py

apps/api/app/api/positions.py

apps/api/app/services/risk_engine.py

apps/worker/app/engine/execution_runtime.py

apps/worker/app/engine/binance_client.py

apps/worker/app/engine/ibkr_client.py

Todos estos deben seguir tratándose como módulos protegidos.

15. Propósito de este documento

Este documento existe para:

hacer explícitas las defensas actuales

facilitar auditorías futuras

evitar cambios que debiliten guardas críticas

ayudar a ingenieros y agentes a entender qué protege al sistema hoy

Cualquier cambio en estas defensas debe reflejarse también aquí.
