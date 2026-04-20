# Intent Architecture Migration

## Context

Sistema de trading multi-broker (Binance + IBKR) con dinero real.

Problema detectado:
- Binance usa `idempotency_key` como pseudo-intent en su arranque de execution.
- IBKR usa un intent semántico más fuerte.
- `intent_consumptions` está siendo usada con doble semántica:
  - Binance: correlación mínima
  - IBKR: estado operativo y reconciliación
- `open_from_signal` no constituye carril real validado de trading end-to-end.

Conclusión base:
El inicio del pipeline no está homogéneo entre brokers y debe corregirse.

---

## Restricciones fijas del trabajo

- NO tocar `ops.py`
- Mantener cada broker separado en su implementación total
- NO tocar IBKR salvo necesidad técnica real explícitamente justificada
- NO mezclar Binance con IBKR en implementación
- NO usar `idempotency_key` como sustituto conceptual de Intent
- NO ejecutar broker sin Intent persistido
- NO crear posición interna como sustituto de execution real
- Todo debe ser incremental, aditivo, auditable y verificable

---

## Decisión arquitectónica

Separar claramente:

1. `intents`
   - fuente de verdad financiera
   - representa qué se quiso hacer antes de cualquier consumo o execution

2. `intent_consumptions`
   - tabla downstream operativa
   - representa qué broker tomó el intent y cómo quedó correlacionado con execution

3. `intent_idempotency_aliases`
   - compatibilidad temporal para Binance
   - permite mapear `idempotency_key` heredado hacia `intent_id`

Regla central:
- `intent_id` es la única identidad maestra
- `idempotency_key` es solo alias técnico temporal

---

## Modelo objetivo del pipeline

Intent -> IntentConsumption -> Execution -> Broker -> Trades -> Fills -> Reconciliation

---

## Contrato final congelado: tabla `intents`

Propósito:
Fuente de verdad del origen financiero antes de cualquier consumo o execution.

Columnas mínimas obligatorias:
- `intent_id`
- `user_id`
- `broker`
- `account_id`
- `symbol`
- `side`
- `expected_qty`
- `order_type`
- `source`
- `lifecycle_status`
- `created_at`
- `updated_at`

Columnas opcionales futuras:
- `metadata_json`
- `failure_reason`
- `strategy_id` / `module`
- `risk_profile`
- `stop_loss`
- `take_profit`

Estados permitidos:
- `CREATED`
- `CONSUMED`
- `EXECUTED`
- `PARTIALLY_FILLED`
- `FILLED`
- `FAILED`
- `CANCELLED`

Reglas:
- el intent se crea siempre antes de execution
- el intent no depende del runtime del broker
- el intent no depende de `idempotency_key`
- el intent es la única fuente de verdad del “qué se quiso hacer”

---

## Contrato final congelado: tabla `intent_consumptions`

Propósito:
Representar la toma del intent por un broker/contexto y su enlace con execution, estado operativo y reconciliación.

Columnas mínimas obligatorias:
- `intent_id`
- `consumer`
- `broker`
- `account_id`
- `status`
- `consumed_at`
- `updated_at`

Columnas operativas obligatorias al ejecutar:
- `execution_ref`
- `execution_ref_type`

Columnas operativas recomendadas:
- `filled_qty`
- `remaining_qty`
- `avg_fill_price`
- `last_broker_status`
- `error_code`
- `error_detail`
- `market`
- `symbol`
- `side`
- `expected_qty`

Estados operativos permitidos:
- `CONSUMED`
- `EXECUTING`
- `EXECUTED`
- `PARTIALLY_FILLED`
- `FILLED`
- `FAILED`
- `CANCELLED`

Reglas:
- `intent_consumptions` depende de `intents.intent_id`
- nunca es fuente de verdad financiera
- solo representa consumo, correlación y estado operativo downstream

---

## Contrato final congelado: tabla `intent_idempotency_aliases`

Propósito:
Persistir el vínculo técnico temporal entre `idempotency_key` heredado e `intent_id` nuevo.

Columnas mínimas obligatorias:
- `id`
- `intent_id`
- `user_id`
- `endpoint`
- `idempotency_key`
- `created_at`
- `updated_at`

Reglas:
- `intent_id` manda siempre
- `idempotency_key` solo apunta a `intent_id`
- nunca usar alias como fuente de verdad
- esta tabla es temporal de transición, no financiera

---

## Fases congeladas

### F0 — Contrato congelado
Objetivo:
Cerrar diseño y reglas sin tocar código.

Estado:
Cerrada.

### F1 — Crear tabla `intents`
Objetivo:
Introducir la fuente de verdad financiera.

Alcance:
- solo DB
- solo cambio aditivo
- no tocar runtime
- no tocar `intent_consumptions`
- no tocar `ops.py`

Estado:
Definida, pendiente implementación.

### F2 — Crear tabla `intent_idempotency_aliases`
Objetivo:
Compatibilidad temporal Binance entre `idempotency_key` e `intent_id`.

Alcance:
- solo DB
- solo cambio aditivo
- no tocar runtime
- no tocar `ops.py`
- no tocar IBKR

Estado:
Definida, pendiente implementación.

### F3 — `intent_service`
Objetivo:
Crear módulo externo para manejar el lifecycle del Intent.

Archivo propuesto:
`apps/api/app/services/intent_service.py`

Responsabilidad:
- `create_intent(...)`
- `get_intent(...)`
- `assert_intent_exists(...)`
- `mark_intent_consumed(...)`
- `mark_intent_executed(...)`
- `mark_intent_failed(...)`
- `mark_intent_filled(...)`
- `mark_intent_cancelled(...)`

Regla:
No ejecuta broker, no consume intent, no reconcilia fills, no toca `ops.py`.

Estado:
Definida, pendiente implementación.

### F4 — `binance_intent_adapter`
Objetivo:
Crear Intent semántico para Binance antes de llamar al runtime actual.

Archivo propuesto:
`apps/api/app/services/binance_intent_adapter.py`

Responsabilidad:
- validar input mínimo
- crear intent vía `intent_service`
- registrar alias temporal si viene `idempotency_key`
- llamar al runtime actual pasando `intent_id` como `intent_key`

Regla:
No toca gateway, no toca broker directamente, no toca `ops.py`.

Estado:
Definida, pendiente implementación.

### F5 — Integración Binance con runtime actual
Objetivo:
Hacer que Binance deje de arrancar desde pseudo-intent y pase a arrancar desde `intent_id`.

Estado:
Definida, pendiente implementación.

### F6 — Revisión mínima de compatibilidad IBKR
Objetivo:
Validar si hace falta ajuste menor de naming o ninguno.

Regla:
No tocar IBKR salvo necesidad técnica real.

Estado:
Definida, pendiente implementación.

---

## Hallazgos técnicos confirmados

### Binance
- execution real entra por `execute_binance_test_order_for_user(...)`
- actualmente recibe `intent_key=idempotency_key`
- inserta registro mínimo en `intent_consumptions`
- adjunta execution vía `client_order_id`
- `_build_binance_client_order_id(...)` deriva identidad determinística con:
  - user_id
  - symbol
  - side
  - qty
  - market
  - intent_key

### IBKR
- genera intent semántico explícito con `generate_internal_ibkr_intent_key(...)`
- usa `IntentConsumptionStore` y `get_consumption_record(...)`
- usa `intent_consumptions` para:
  - correlación intent -> execution_ref
  - reconciliación
  - validaciones operativas (por ejemplo SELL guard)

### Conclusión comparativa
- IBKR implementa mejor el modelo de Intent
- Binance recupera parte de la trazabilidad más tarde, pero arranca peor
- como ambos comparten persistencia conceptual, conviene elevar Binance al estándar IBKR en el origen

---

## Estrategia de transición

Regla:
No reemplazo brusco. Solo convivencia temporal controlada.

Orden:
1. crear `intents`
2. crear `intent_idempotency_aliases`
3. implementar `intent_service`
4. implementar `binance_intent_adapter`
5. pasar `intent_id` al runtime Binance actual
6. revisar si IBKR necesita ajuste menor o ninguno

---

## Estado actual

- Diseño congelado
- Contratos de `intents`, `intent_consumptions` y `intent_idempotency_aliases` cerrados
- F1, F2, F3, F4, F5, F6 definidos
- Documentación persistida en repo
- Pendiente implementación futura por fases

