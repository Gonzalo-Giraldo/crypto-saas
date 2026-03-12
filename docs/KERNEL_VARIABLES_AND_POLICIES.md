# KERNEL_VARIABLES_AND_POLICIES.md

## 1. Propósito

Este documento define las **variables, parámetros y políticas** que gobiernan el comportamiento del kernel de trading.

El objetivo es que el sistema evolucione hacia un modelo donde gran parte de sus mejoras y ajustes se realicen mediante:

- configuración
- thresholds
- prioridades
- pesos
- multiplicadores
- activación/desactivación de módulos

y no exclusivamente mediante cambios directos en el código.

Este documento complementa:

- `docs/MODULE_DECISION_CONTRACT.md`
- `docs/KERNEL_ORCHESTRATION_MODEL.md`
- `docs/KERNEL_EXECUTION_PIPELINE.md`
- `docs/OPERATIONAL_MODULES_MODEL.md`
- `docs/MARKET_CONTEXT_MODULES_MODEL.md`
- `docs/LEARNING_MODULE_MODEL.md`

---

## 2. Principio central

El kernel debe ser **estable**, mientras que gran parte del comportamiento del sistema debe estar gobernado por variables explícitas.

Esto permite:

- mejorar estrategias sin reescribir el kernel
- probar ajustes de forma controlada
- adaptar comportamiento por mercado
- facilitar operación de capital propio
- preparar evolución futura hacia SaaS

No todo debe ser configurable.  
Las invariantes de seguridad deben permanecer rígidas.

---

## 3. Categorías de variables

Las variables del sistema pueden agruparse en las siguientes categorías:

1. variables de activación
2. variables de scoring
3. variables de sizing
4. variables de exposición y riesgo
5. variables de contexto de mercado
6. variables del módulo de aprendizaje
7. variables de orquestación del kernel
8. variables de ejecución
9. variables de auditoría y observabilidad

---

## 4. Variables de activación

Estas variables controlan qué partes del sistema están activas.

Ejemplos:

- `AUTO_PICK_INTERNAL_SCHEDULER_ENABLED`
- `AUTO_PICK_REAL_GUARD_ENABLED`
- `LEARNING_MODULE_ENABLED`
- `MARKET_TREND_MODULE_ENABLED`
- `SELL_DECISION_MODULE_ENABLED`
- `NEWS_CONTEXT_MODULE_ENABLED` (futuro)

### Objetivo

Permitir que módulos y comportamientos puedan:

- activarse
- desactivarse
- probarse por etapas

sin reescribir la arquitectura.

---

## 5. Variables de scoring

Estas variables controlan cómo se forma el score final del candidato.

Ejemplos:

- `MIN_SCORE_PCT`
- `BUY_SCORE_THRESHOLD`
- `SELL_SCORE_THRESHOLD`
- `TREND_SCORE_BONUS`
- `TREND_CONFLICT_PENALTY`
- `LEARNING_SCORE_DELTA_MAX`
- `REGIME_SCORE_ADJUSTMENT`

### Objetivo

Ajustar la sensibilidad del sistema a:

- calidad de señal
- contexto de mercado
- confirmación de tendencia
- aprendizaje histórico

---

## 6. Variables de sizing

Estas variables gobiernan la cantidad final aprobada.

Ejemplos:

- `BASE_QTY_BINANCE`
- `BASE_QTY_IBKR`
- `LIQUIDITY_GREEN_MULTIPLIER`
- `LIQUIDITY_GRAY_MULTIPLIER`
- `LIQUIDITY_RED_MULTIPLIER`
- `SELL_QTY_MULTIPLIER`
- `LEARNING_QTY_MULTIPLIER_MIN`
- `LEARNING_QTY_MULTIPLIER_MAX`

### Objetivo

Permitir que el sizing evolucione sin esconder reglas en hardcodes.

### Regla importante

La política de sizing debe tender a estar definida por variables explícitas y no por valores mágicos dispersos.

---

## 7. Variables de exposición y riesgo

Estas variables definen límites duros del sistema.

Ejemplos:

- `MAX_OPEN_QTY_PER_SYMBOL`
- `MAX_OPEN_NOTIONAL_PER_EXCHANGE`
- `MAX_OPEN_POSITIONS`
- `MAX_DAILY_TRADES`
- `DAILY_RISK_LIMIT`
- `MAX_RISK_PER_TRADE`

### Objetivo

Controlar:

- exposición
- concentración
- frecuencia operativa
- riesgo diario

### Observación

Estas variables son más cercanas a **política operativa dura** que a simple tuning.

---

## 8. Variables de contexto de mercado

Estas variables gobiernan cómo se interpreta el estado del mercado.

Ejemplos:

- `MAX_SPREAD_BPS`
- `MAX_SLIPPAGE_BPS`
- `TREND_LOOKBACK_WINDOW`
- `REGIME_LOOKBACK_WINDOW`
- `VOLATILITY_THRESHOLD_HIGH`
- `VOLATILITY_THRESHOLD_LOW`

### Objetivo

Permitir que el sistema adapte su lectura del mercado sin alterar la estructura del kernel.

---

## 9. Variables del módulo de aprendizaje

Estas variables gobiernan la influencia del aprendizaje.

Ejemplos:

- `LEARNING_CONFIDENCE_MIN`
- `LEARNING_SCORE_BOOST_MAX`
- `LEARNING_SCORE_PENALTY_MAX`
- `LEARNING_QTY_REDUCTION_MAX`
- `LEARNING_LOOKBACK_WINDOW`
- `LEARNING_PATTERN_MIN_OBSERVATIONS`

### Objetivo

Evitar que el módulo de aprendizaje:

- reaccione exageradamente
- se sobreajuste
- domine decisiones sin evidencia suficiente

---

## 10. Variables de orquestación del kernel

Estas variables gobiernan cómo el kernel agrega decisiones.

Ejemplos:

- `MODULE_PRIORITY_HARD_SAFETY`
- `MODULE_PRIORITY_EXPOSURE`
- `MODULE_PRIORITY_SESSION`
- `MODULE_PRIORITY_LIQUIDITY`
- `MODULE_PRIORITY_LEARNING`
- `MODULE_PRIORITY_MARKET_TREND`

También pueden existir variables como:

- `ALLOW_QTY_OVERRIDE_FROM_LEARNING`
- `ALLOW_SCORE_STACKING`
- `ALLOW_WARN_STATE_EXECUTION`

### Objetivo

Permitir que la gobernanza del kernel sea:

- explícita
- ajustable
- auditada

---

## 11. Variables de ejecución

Estas variables gobiernan cómo se comporta la capa final de ejecución.

Ejemplos:

- `REQUIRE_IDEMPOTENCY_FOR_DRY_RUN`
- `REQUIRE_EXIT_PLAN_FOR_REAL_EXECUTION`
- `BINANCE_GATEWAY_STRICT_MODE`
- `BROKER_RETRY_MAX_ATTEMPTS`
- `BROKER_RETRY_BACKOFF_MS`
- `CLIENT_ORDER_ID_MODE`

### Objetivo

Controlar:

- seguridad de ejecución
- retries
- comportamiento de broker
- guardrails live

---

## 12. Variables de auditoría y observabilidad

Estas variables controlan cuánto y cómo registra el sistema.

Ejemplos:

- `AUDIT_MODULE_DECISIONS_ENABLED`
- `AUDIT_FINAL_DECISION_ENABLED`
- `AUDIT_BROKER_RESPONSE_ENABLED`
- `LOG_SCHEDULER_TICKS_ENABLED`
- `LOG_LEARNING_ADJUSTMENTS_ENABLED`

### Objetivo

Asegurar trazabilidad suficiente sin generar ruido excesivo.

---

## 13. Qué debe ser configurable

Debe tender a ser configurable:

- scoring
- thresholds de liquidez
- multiplicadores de sizing
- pesos de módulos
- score bonuses/penalties
- ventanas de aprendizaje
- prioridades de agregación
- activación de módulos

---

## 14. Qué NO debe ser configurable libremente

No debe quedar abierto a configuración blanda:

- tenant isolation
- idempotencia crítica
- signal lifecycle válido
- paper/live separation
- auditabilidad mínima
- restricciones esenciales de seguridad

Estas son invariantes del sistema.

---

## 15. Reglas de diseño de variables

Toda variable nueva debería cumplir estas reglas:

1. tener nombre explícito
2. tener propósito claro
3. tener rango esperado
4. tener impacto identificable
5. ser auditable
6. no duplicar otra variable ya existente

Si una variable no cumple estas condiciones, probablemente no debería existir todavía.

---

## 16. Estructura recomendada de políticas

Las políticas deberían poder agruparse por familia.

### 16.1 Política de mercado
- liquidez
- spread
- slippage
- sesiones
- reglas de contexto

### 16.2 Política de estrategia
- score mínimo
- score bonuses
- filtros de tendencia
- filtros de régimen

### 16.3 Política de sizing
- qty base
- multiplicadores
- overrides permitidos

### 16.4 Política de riesgo
- exposición
- posiciones máximas
- riesgo diario
- límites por símbolo

### 16.5 Política de aprendizaje
- confianza mínima
- ventanas históricas
- penalizaciones/bonos máximos

### 16.6 Política de ejecución
- idempotencia
- retries
- guardrails live
- reconciliación

---

## 17. Ejemplos conceptuales

### Ejemplo 1 — liquidez más conservadora

```text
LIQUIDITY_GRAY_MULTIPLIER = 0.35
MAX_SPREAD_BPS = 18
MAX_SLIPPAGE_BPS = 20

Ejemplo 2 — SELL más prudente
SELL_QTY_MULTIPLIER = 0.20
SELL_SCORE_THRESHOLD = 72
Ejemplo 3 — aprendizaje menos agresivo
LEARNING_SCORE_BOOST_MAX = 2
LEARNING_QTY_REDUCTION_MAX = 0.15
LEARNING_PATTERN_MIN_OBSERVATIONS = 25
18. Beneficios del modelo gobernado por variables

Este enfoque aporta:

menor dependencia del código central

ajustes operativos más rápidos

experimentación más segura

mejor auditabilidad

mejor escalabilidad futura

También permite que parte de la evolución del sistema pueda realizarse mediante:

configuración controlada

pruebas graduales

tuning supervisado

19. Riesgos de este enfoque

También existen riesgos:

exceso de variables

políticas contradictorias

tuning desordenado

cambios sin suficiente validación

pérdida de claridad si no se documentan bien

Por eso toda variable importante debe estar:

documentada

versionada

justificada

auditada

20. Regla final

El kernel debe evolucionar hacia un sistema donde:

la arquitectura sea estable

las políticas sean explícitas

las variables sean comprensibles

la seguridad siga siendo rígida

los cambios operativos no requieran tocar siempre el código

Ese es el modelo correcto para una plataforma que quiere:

operar capital propio primero

madurar como SaaS después.
