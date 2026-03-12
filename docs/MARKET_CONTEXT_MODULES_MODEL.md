# MARKET_CONTEXT_MODULES_MODEL.md

## 1. Propósito

Este documento define los **módulos de contexto de mercado** del sistema de trading.

Estos módulos analizan el estado del mercado y producen información que ayuda al kernel a tomar decisiones más informadas.

A diferencia de los módulos operativos, los módulos de contexto:

- no ejecutan órdenes
- no deciden directamente abrir o cerrar posiciones
- aportan información contextual que puede modificar score, confianza o sizing

Todos los módulos deben cumplir el contrato definido en:

docs/MODULE_DECISION_CONTRACT.md

---

# 2. Rol dentro del sistema

Los módulos de contexto operan en la etapa temprana del pipeline del kernel.

Flujo conceptual:

Signal / Candidate  
↓  
Market Context Modules  
↓  
Operational Modules  
↓  
Kernel Decision  
↓  
Execution Layer

Estos módulos enriquecen el `ModuleContext` antes de que los módulos operativos tomen decisiones.

---

# 3. Principios de diseño

Los módulos de contexto deben cumplir:

- independencia funcional
- explicabilidad
- bajo acoplamiento
- compatibilidad con el contrato de módulos
- neutralidad operativa

Esto significa que los módulos de contexto **no deben bloquear operaciones por sí mismos**, excepto en casos extremos definidos por política.

---

# 4. Lista de módulos de contexto

Los módulos actuales o planificados incluyen:

1. Market Trend Module
2. Market Regime Module
3. Market State Module
4. News Context Module (futuro)
5. Volatility Context Module (futuro)

---

# 5. Market Trend Module

## Propósito

Detectar la **dirección predominante del mercado** para un activo o conjunto de activos.

Este módulo ayuda al sistema a identificar si el mercado se encuentra en:

- tendencia alcista
- tendencia bajista
- mercado lateral
- tendencia incierta

## Responsabilidades

- analizar series de precio
- detectar dirección de tendencia
- clasificar fuerza de tendencia
- aportar señal contextual al kernel

## Estados típicos de tendencia

- bullish
- bearish
- neutral
- unclear

## Entrada relevante

Desde `ModuleContext`:

- symbol
- market_profile
- price_series
- timeframe
- runtime_policy

## Salida típica


ModuleDecision
module_id: market_trend
module_type: market_context
decision_status: PASS
score_delta: +/- valor
reason_codes:

TREND_BULLISH

TREND_BEARISH

TREND_NEUTRAL
output_variables:
trend_bias: bullish/bearish/neutral


## Uso dentro del kernel

El kernel puede utilizar el resultado para:

- aumentar score en dirección de tendencia
- reducir score si la señal contradice la tendencia
- ajustar sizing

---

# 6. Market Regime Module

## Propósito

Clasificar el **régimen actual del mercado**.

Esto permite adaptar el comportamiento del sistema a diferentes condiciones.

## Regímenes típicos

- trending
- ranging
- volatile
- low_volatility

## Entrada relevante

- market volatility
- trend signals
- liquidity state
- historical price behavior

## Salida típica


ModuleDecision
module_id: market_regime
decision_status: PASS
output_variables:
regime: trending/ranging/volatile
reason_codes:

REGIME_TRENDING

REGIME_RANGING


## Uso dentro del kernel

El régimen puede influir en:

- scoring
- estrategia activa
- tamaño de posición

---

# 7. Market State Module

## Propósito

Clasificar el **estado actual del mercado**.

Esto puede incluir factores como:

- liquidez general
- estabilidad
- presencia de shocks

## Estados típicos

- normal
- stressed
- illiquid
- unstable

## Entrada relevante

- spread
- volatility
- market depth
- slippage

## Salida típica


ModuleDecision
module_id: market_state
decision_status: PASS
output_variables:
market_state: normal/stressed/illiquid
reason_codes:

MARKET_STATE_NORMAL

MARKET_STATE_STRESSED


---

# 8. News Context Module (futuro)

## Propósito

Incorporar el impacto potencial de **noticias relevantes** en el activo.

Este módulo podría analizar:

- noticias macro
- noticias del activo
- eventos regulatorios
- eventos corporativos

## Uso potencial

- reducir score en eventos de alto riesgo
- bloquear trading temporalmente
- reducir tamaño de posición

Este módulo debe implementarse con cuidado debido a:

- ruido informativo
- latencia de datos
- dificultad de clasificación.

---

# 9. Volatility Context Module (futuro)

## Propósito

Analizar el nivel de **volatilidad del mercado**.

Esto puede ayudar a:

- ajustar tamaño de posiciones
- reducir exposición en condiciones extremas
- detectar condiciones anormales

## Salida típica


ModuleDecision
module_id: volatility
decision_status: PASS/WARN
qty_multiplier: valor
reason_codes:

VOLATILITY_HIGH

VOLATILITY_NORMAL


---

# 10. Interacción con módulos operativos

Los módulos de contexto no reemplazan a los módulos operativos.

Su función es **alimentar información adicional**.

Ejemplo:

Market Trend → aumenta score  
Liquidity Module → reduce qty  
Exposure Module → bloquea operación  

El kernel agrega estas decisiones para producir la decisión final.

---

# 11. Relación con Market Profiles

El comportamiento de los módulos de contexto puede variar según el perfil de mercado definido en:

docs/MARKET_PROFILES_MODEL.md

Ejemplos:

### Crypto

- mercados 24/7
- mayor volatilidad
- mayor importancia del régimen de mercado

### Equities

- sesiones de mercado definidas
- eventos corporativos relevantes
- mayor impacto de noticias

---

# 12. Evolución futura

El sistema puede incorporar nuevos módulos de contexto sin alterar el kernel.

Ejemplos futuros:

- macro economic context
- sector performance context
- order flow analysis
- sentiment analysis

Todos deben cumplir el contrato definido en:

docs/MODULE_DECISION_CONTRACT.md

---

# 13. Beneficios del modelo

Este enfoque permite:

- separar análisis de mercado de ejecución
- mantener decisiones explicables
- agregar inteligencia gradualmente
- evitar acoplamiento excesivo

---

# 14. Nota final

Los módulos de contexto son responsables de **entender el mercado**.

Los módulos operativos son responsables de **decidir la operación**.

El kernel es responsable de **combinar ambos mundos para producir una decisión segura y auditable**.
