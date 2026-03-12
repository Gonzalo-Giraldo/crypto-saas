# LEARNING_MODULE_MODEL.md

## 1. Propósito

El módulo de aprendizaje permite que el sistema mejore sus decisiones con el tiempo mediante el análisis del desempeño histórico de operaciones.

Su función es analizar:

- decisiones pasadas
- resultados de operaciones
- comportamiento del mercado
- degradación o mejora de patrones

y aportar ajustes al proceso de decisión del kernel.

El módulo de aprendizaje no ejecuta órdenes ni reemplaza al kernel.  
Su función es **modular decisiones futuras mediante información histórica**.

---

# 2. Rol dentro de la arquitectura

El módulo de aprendizaje pertenece a la categoría de:

Adaptive Intelligence Modules

Estos módulos analizan información histórica y producen ajustes en:

- score
- confianza
- sizing
- elegibilidad de patrones

Flujo conceptual:


Signal / Candidate
↓
Market Context Modules
↓
Operational Modules
↓
Learning Module
↓
Kernel Decision Aggregation
↓
FinalTradingDecision


---

# 3. Principios de diseño

El módulo de aprendizaje debe cumplir los siguientes principios:

- explicabilidad
- auditabilidad
- reversibilidad
- bajo acoplamiento
- compatibilidad con `ModuleDecisionContract`

El aprendizaje **no puede romper las defensas duras del sistema**, como:

- límites de exposición
- sesiones de mercado
- restricciones de broker
- invariantes de seguridad

---

# 4. Datos utilizados por el aprendizaje

El sistema puede utilizar múltiples fuentes de información histórica.

Ejemplos de estructuras existentes:

### LearningDecisionSnapshot

Registro del contexto de decisión en el momento en que se evaluó una operación.

Incluye:

- contexto de mercado
- score de decisión
- módulos activos
- parámetros de decisión

---

### LearningDecisionOutcome

Registro del resultado de una decisión.

Incluye:

- operación ejecutada
- resultado financiero
- condiciones de mercado posteriores
- éxito o fallo del patrón

---

### LearningRollupHourly

Agregación periódica de resultados.

Puede incluir métricas como:

- tasa de éxito
- retorno promedio
- drawdown reciente
- estabilidad de patrones

---

# 5. Tipos de aprendizaje posibles

El módulo puede implementar distintos enfoques.

## Aprendizaje basado en desempeño

Analiza si decisiones similares han sido exitosas recientemente.

Ejemplo:

- patrón similar tuvo pérdidas recientes
- reducir score o tamaño

---

## Aprendizaje basado en degradación de patrón

Detecta si una estrategia está perdiendo eficacia.

Ejemplo:

- caída en tasa de éxito
- aumento de volatilidad adversa

---

## Aprendizaje basado en contexto de mercado

Analiza si ciertas estrategias funcionan mejor en determinados regímenes.

Ejemplo:

- estrategia funciona mejor en mercados con tendencia

---

# 6. Entrada relevante del módulo

El módulo recibe `ModuleContext`.

Campos relevantes incluyen:

- symbol
- market_profile
- trend_state
- candidate_score
- candidate_qty
- runtime_policy

También puede consultar:

- snapshots históricos
- outcomes recientes
- métricas agregadas

---

# 7. Salida del módulo

El módulo devuelve un `ModuleDecision`.

Ejemplo conceptual:


ModuleDecision
module_id: learning
module_type: adaptive_intelligence
decision_status: PASS/WARN/FAIL
score_delta: valor
qty_multiplier: valor
reason_codes:

LEARNING_CONFIDENCE_HIGH

LEARNING_CONFIDENCE_LOW

LEARNING_PATTERN_DEGRADED
output_variables:
learning_confidence: high/medium/low


---

# 8. Ejemplos de comportamiento

### Caso 1 — patrón confirmado

Resultados históricos positivos.


score_delta: +3
qty_multiplier: 1.1
reason_codes:

LEARNING_PATTERN_CONFIRMED


---

### Caso 2 — patrón degradado

Resultados recientes negativos.


score_delta: -6
qty_multiplier: 0.6
reason_codes:

LEARNING_PATTERN_DEGRADED


---

### Caso 3 — alta incertidumbre

Datos insuficientes o contradictorios.


decision_status: WARN
score_delta: -2
reason_codes:

LEARNING_LOW_CONFIDENCE


---

# 9. Limitaciones del aprendizaje

El aprendizaje **no debe tomar control absoluto del sistema**.

Debe respetar siempre:

- reglas de riesgo
- exposición máxima
- restricciones de broker
- sesión de mercado

El aprendizaje puede influir en decisiones, pero no puede violar estas restricciones.

---

# 10. Evitar sobreajuste

El sistema debe evitar adaptar decisiones demasiado rápido.

Para esto pueden utilizarse:

- ventanas de tiempo mínimas
- suavización de métricas
- validación cruzada de señales
- límites de ajuste de score o tamaño

Esto evita que el sistema reaccione excesivamente a eventos aislados.

---

# 11. Auditoría del aprendizaje

El módulo debe registrar:

- qué datos utilizó
- qué ajuste realizó
- por qué realizó ese ajuste
- impacto en la decisión final

Esto permite analizar si el aprendizaje está mejorando o empeorando el sistema.

---

# 12. Relación con módulos de contexto

El aprendizaje puede combinarse con módulos como:

- Market Trend Module
- Market Regime Module
- Volatility Module

Esto permite que el sistema aprenda **qué estrategias funcionan mejor en diferentes condiciones de mercado**.

---

# 13. Evolución futura

El módulo puede evolucionar para incluir:

- aprendizaje basado en clustering de mercados
- clasificación de patrones
- análisis de portafolio
- aprendizaje multi-mercado

Estas mejoras deben mantenerse compatibles con el contrato modular del sistema.

---

# 14. Nota final

El módulo de aprendizaje convierte el sistema en un motor capaz de **adaptarse a cambios del mercado**.

Sin embargo, su función es complementar la decisión del kernel, no reemplazarla.

El kernel sigue siendo la autoridad final sobre la decisión de trading.
