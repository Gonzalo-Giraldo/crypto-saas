# MINIMAL_CORE_BASELINE.md

## 1. Propósito
Establecer el baseline mínimo, limpio y verificable del núcleo funcional del sistema en Python 3.11, garantizando superficie de incertidumbre = 0 y exclusión explícita de componentes contaminados o ambiguos.

## 2. Componentes incluidos
- apps/api/app/services/idempotency.py
- apps/worker/app/engine/market_data_engine.py
- apps/worker/app/engine/risk_engine.py
- apps/worker/app/engine/portfolio_engine.py
- apps/worker/app/engine/minimal_execution_runtime.py

## 3. Componentes excluidos
- apps/worker/app/engine/execution_runtime.py
- apps/worker/app/engine/binance_client.py
- apps/worker/app/engine/ibkr_client.py
- apps/worker/app/engine/broker_registry.py
- cualquier otro archivo no listado en la sección 2

## 4. Contrato de `MinimalExecutionRuntime`
- Clase: `MinimalExecutionRuntime`
- Método: `submit_intent(...)`
- Input mínimo:
  - user_id
  - strategy_id
  - broker (solo 'binance' permitido)
  - market
  - symbol (no vacío)
  - side ('BUY'/'SELL')
  - quantity (>0)
  - order_ref (no vacío)
  - mode (solo 'stub' permitido)
  - metadata (opcional)
- Reglas:
  1. order_ref obligatorio
  2. broker solo 'binance'
  3. mode solo 'stub'
  4. quantity > 0
  5. symbol no vacío
  6. side normalizado ('BUY'/'SELL')
  7. pasa por RiskEngine
  8. si risk rechaza, no hay submission
  9. idempotencia local en memoria por (user_id, order_ref)
  10. nunca actualiza portfolio
  11. nunca afirma fill
- Output mínimo:
  - accepted
  - stage
  - reason
  - broker
  - symbol
  - side
  - quantity
  - order_ref
  - idempotency_status
  - risk_status
  - submission_status
  - fill_status
  - portfolio_effect_applied

## 5. Garantías actuales
- El núcleo compila y pasa smoke mínimo en Docker Python 3.11
- El runtime rechaza inputs inválidos (order_ref vacío, quantity <= 0, side inválido)
- No hay dependencia de runtime, broker_registry, binance_client ni ibkr_client
- No hay lógica de fills ni actualización de portfolio
- Idempotencia garantizada solo en memoria y solo para la vida útil del objeto

## 6. No-garantías actuales
- No hay soporte para IBKR
- No hay multi-broker real
- No hay fills ni ejecución real
- No hay persistencia de idempotencia
- No hay integración con base de datos ni broker
- No hay garantías de dinero real ni de producción
- No hay cobertura de tests automatizados

## 7. Límites operativos
- Solo Python 3.11 validado en Docker
- Solo broker 'binance' y mode 'stub' permitidos
- Solo núcleo listado en sección 2 soportado
- No usar este baseline para operaciones reales ni dinero real

## 8. Siguiente fase recomendada
- Definir y validar contratos de integración para runtime extendido
- Introducir tests automatizados para el núcleo
- Documentar escenarios de error y bordes
- Planificar reintegración progresiva de componentes excluidos bajo control forense
