nano docs/OPERATIONAL_MODULES_MODEL.md

y pega esto.

# OPERATIONAL_MODULES_MODEL.md

## 1. Propósito

Este documento define los **módulos operativos principales** del sistema de trading.

Estos módulos son responsables de analizar diferentes aspectos de una operación potencial y emitir una decisión parcial mediante:


ModuleDecision


según el contrato definido en:


docs/MODULE_DECISION_CONTRACT.md


Cada módulo analiza un aspecto específico del sistema y devuelve una decisión homogénea que el kernel agrega para producir la decisión final.

---

# 2. Filosofía de módulos operativos

Los módulos operativos deben cumplir los siguientes principios:

- responsabilidad única
- decisiones explicables
- independencia funcional
- compatibilidad con el contrato de módulos
- auditabilidad

Los módulos **no ejecutan órdenes**, solo producen decisiones.

El kernel es el único responsable de producir la decisión final.

---

# 3. Lista de módulos operativos base

Los módulos operativos base del sistema son:

1. Buy Decision Module
2. Sell Decision Module
3. Liquidity Module
4. Exposure Module
5. Balance Module
6. Session Module
7. Sizing Module

Cada uno analiza un aspecto diferente de la operación.

---

# 4. Buy Decision Module

## Propósito

Determinar si existe una **condición válida para abrir una posición larga (BUY)**.

Este módulo analiza la calidad de la señal y condiciones del mercado.

## Responsabilidades

- validar señal de compra
- evaluar score mínimo
- validar condiciones básicas de mercado
- confirmar que la oportunidad cumple criterios de estrategia

## Entrada relevante

Desde `ModuleContext`:

- candidate_score
- market_state
- trend_state
- runtime_policy
- signal_source

## Salida típica


ModuleDecision
module_id: buy_decision
decision_status: PASS/WARN/FAIL
score_delta: +/- valor
allow_trade: true/false
reason_codes: [...]


---

# 5. Sell Decision Module

## Propósito

Determinar si existe una **condición válida para abrir una posición corta (SELL)**.

Este módulo evalúa si el mercado permite una estrategia de venta.

## Responsabilidades

- validar señal de venta
- validar compatibilidad con perfil de mercado
- validar condiciones de liquidez
- confirmar reglas de estrategia

## Entrada relevante

- candidate_score
- trend_state
- market_profile
- runtime_policy

## Salida típica


ModuleDecision
module_id: sell_decision
decision_status: PASS/WARN/FAIL
score_delta: +/- valor
allow_trade: true/false
reason_codes: [...]


---

# 6. Liquidity Module

## Propósito

Evaluar si existe suficiente **liquidez de mercado** para ejecutar la operación de forma segura.

## Responsabilidades

- analizar spread
- analizar slippage estimado
- clasificar liquidez

## Clasificación típica

- green
- gray
- red

## Entrada relevante

- spread_bps
- slippage_bps
- runtime_policy

## Salida típica


ModuleDecision
module_id: liquidity
decision_status: PASS/WARN/FAIL
qty_multiplier: valor
reason_codes:

LIQUIDITY_GREEN

LIQUIDITY_GRAY

LIQUIDITY_RED


---

# 7. Exposure Module

## Propósito

Garantizar que la operación no exceda los límites de **exposición de riesgo**.

Este es uno de los módulos de seguridad más críticos.

## Responsabilidades

- verificar cantidad máxima por símbolo
- verificar exposición total por exchange
- verificar número máximo de posiciones abiertas

## Entrada relevante

- open_positions_count
- open_qty_symbol
- open_notional_exchange
- risk_profile
- runtime_policy

## Salida típica


ModuleDecision
module_id: exposure
decision_status: PASS/FAIL
block_trade: true/false
reason_codes:

EXPOSURE_LIMIT_REACHED

SYMBOL_QTY_LIMIT_REACHED


---

# 8. Balance Module

## Propósito

Validar que existe **capital disponible suficiente** para ejecutar la operación.

Este módulo protege contra órdenes que no pueden financiarse.

## Responsabilidades

- validar disponibilidad de capital
- validar saldo del activo base
- validar restricciones del broker

## Entrada relevante

- account_balance
- broker_constraints
- candidate_qty
- price

## Salida típica


ModuleDecision
module_id: balance
decision_status: PASS/FAIL
allow_trade: true/false
reason_codes:

INSUFFICIENT_BALANCE


---

# 9. Session Module

## Propósito

Validar que la operación se realiza durante una **sesión de mercado válida**.

Este módulo es especialmente importante para:

- acciones
- índices
- mercados con horarios definidos

## Responsabilidades

- verificar si el mercado está abierto
- validar restricciones de horario
- validar días de operación

## Entrada relevante

- market_profile
- timestamp
- market_session_rules

## Salida típica


ModuleDecision
module_id: session
decision_status: PASS/FAIL
block_trade: true/false
reason_codes:

MARKET_CLOSED

SESSION_RESTRICTED


---

# 10. Sizing Module

## Propósito

Determinar la **cantidad final de la operación**.

Este módulo calcula la cantidad final considerando:

- tamaño base
- liquidez
- reglas de riesgo
- ajustes de aprendizaje

## Responsabilidades

- calcular qty inicial
- aplicar multiplicadores
- validar restricciones del broker
- producir qty final

## Entrada relevante

- candidate_qty
- qty_multiplier
- runtime_policy
- broker_constraints

## Salida típica


ModuleDecision
module_id: sizing
decision_status: PASS
qty_override: valor
reason_codes:

SIZE_ADJUSTED


---

# 11. Interacción entre módulos

Los módulos no deben depender directamente unos de otros.

La interacción ocurre a través de:


ModuleDecision


El kernel es responsable de combinar decisiones.

Ejemplo:


Liquidity → reduce qty
Exposure → bloquea operación
Learning → reduce score
Trend → aumenta score


El kernel agrega todas las decisiones y produce la resolución final.

---

# 12. Orden sugerido de evaluación

Orden recomendado dentro del kernel:

1. Session Module
2. Exposure Module
3. Balance Module
4. Market Trend Module
5. Buy/Sell Decision Module
6. Liquidity Module
7. Learning Module
8. Sizing Module

Este orden permite detectar problemas críticos temprano.

---

# 13. Evolución futura

Nuevos módulos pueden añadirse sin alterar el kernel si cumplen el contrato.

Ejemplos futuros:

- News Module
- Volatility Module
- Sentiment Module
- Macro Events Module
- Regulatory Alerts Module

Todos deben cumplir:


ModuleDecisionContract


---

# 14. Beneficios del modelo modular

Este modelo permite:

- añadir nuevos tipos de trading
- soportar múltiples brokers
- integrar nuevos mercados
- evolucionar estrategias
- mantener explicabilidad
- reducir riesgo operativo

---

# 15. Nota final

El sistema no debe evolucionar como un bloque monolítico.

Debe evolucionar como un conjunto de módulos especializados que cooperan bajo la orquestación de un kernel estable.

