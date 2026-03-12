# KERNEL_EXECUTION_PIPELINE.md

## 1. Propósito

Este documento describe el **pipeline completo de ejecución del kernel de trading**, desde la recepción de una señal hasta la decisión final de ejecutar una orden.

Este pipeline conecta:

- arquitectura modular
- motor de decisiones
- controles de riesgo
- capa de ejecución

Su objetivo es asegurar que el proceso sea:

- seguro
- auditable
- modular
- predecible

---

# 2. Visión general del pipeline

El proceso de trading sigue las siguientes etapas principales:

1. Signal Intake
2. Candidate Construction
3. Kernel Context Creation
4. Market Context Analysis
5. Operational Evaluation
6. Adaptive Intelligence Adjustment
7. Position Sizing
8. Decision Aggregation
9. Execution Validation
10. Broker Execution

Flujo conceptual:


Signal
↓
Candidate
↓
ModuleContext
↓
Market Context Modules
↓
Operational Modules
↓
Learning Module
↓
Sizing Module
↓
Kernel Decision Aggregation
↓
FinalTradingDecision
↓
Execution Layer


---

# 3. Etapa 1 — Signal Intake

Las señales pueden provenir de múltiples fuentes.

Ejemplos de endpoints:


POST /signals
POST /signals/claim
POST /ops/execution/pretrade/binance/scan
POST /ops/execution/pretrade/ibkr/scan


El sistema valida:

- autenticación
- tenant
- usuario
- formato de señal

Las señales válidas se convierten en **candidatos de trading**.

---

# 4. Etapa 2 — Candidate Construction

Un candidato representa una oportunidad potencial de trading.

Puede generarse a partir de:

- señales manuales
- escáner de mercado
- estrategias automáticas
- universo predefinido

Ejemplo de campos:


candidate
symbol
side
price
qty_base
score_base
metadata


El candidato se convierte en entrada del kernel.

---

# 5. Etapa 3 — Kernel Context Creation

El kernel construye el objeto:


ModuleContext


Este contexto contiene toda la información necesaria para evaluar la operación.

Incluye:

- contexto del mercado
- estado del sistema
- perfil de riesgo
- estado de posiciones
- restricciones del broker

Este contexto es la entrada para todos los módulos.

---

# 6. Etapa 4 — Market Context Analysis

El kernel consulta los **módulos de contexto de mercado**.

Ejemplos:

- Market Trend Module
- Market Regime Module
- Market State Module

Estos módulos analizan condiciones del mercado y devuelven:


ModuleDecision


Ejemplo:


TREND_BULLISH
REGIME_TRENDING
MARKET_STATE_NORMAL


Estos resultados enriquecen el contexto de decisión.

---

# 7. Etapa 5 — Operational Evaluation

El kernel consulta los **módulos operativos**.

Estos módulos analizan si la operación es viable.

Ejemplos:

- Buy Decision Module
- Sell Decision Module
- Liquidity Module
- Exposure Module
- Balance Module
- Session Module

Estos módulos pueden:

- aumentar score
- reducir score
- bloquear la operación

---

# 8. Etapa 6 — Adaptive Intelligence Adjustment

El kernel consulta el **Learning Module**.

Este módulo analiza:

- desempeño histórico
- calidad de patrones
- degradación reciente

Puede ajustar:

- score
- confianza
- multiplicadores de tamaño

El aprendizaje **no puede violar reglas duras del sistema**.

---

# 9. Etapa 7 — Position Sizing

El kernel calcula el tamaño final de la posición.

El cálculo considera:

- cantidad base del candidato
- multiplicadores de liquidez
- ajustes de aprendizaje
- límites de riesgo
- restricciones del broker

Resultado:


approved_qty


---

# 10. Etapa 8 — Decision Aggregation

El kernel agrega todas las decisiones de módulos.

Se evalúan:


score_total
block_trade
qty_final
side_final


Reglas importantes:

- módulos de seguridad tienen prioridad
- exposición puede bloquear operación
- sesión cerrada bloquea operación
- aprendizaje no puede ignorar reglas de seguridad

Resultado:


FinalTradingDecision


---

# 11. Etapa 9 — Execution Validation

Antes de enviar una orden al broker, el sistema verifica:

- idempotency key
- paper/live mode
- trading enabled
- allowlists
- guardias adicionales

Esto previene:

- órdenes duplicadas
- trading accidental
- ejecución en condiciones inseguras

---

# 12. Etapa 10 — Broker Execution

Si la decisión final es positiva, el sistema llama a la capa de ejecución.

Ejemplos:


execute_binance_test_order_for_user
execute_ibkr_test_order_for_user


La capa de ejecución:

- normaliza cantidades
- valida restricciones del broker
- envía la orden

La respuesta del broker se registra para auditoría.

---

# 13. Registro de auditoría

Cada decisión del kernel debe registrar:

- contexto de entrada
- módulos consultados
- decisiones de módulos
- score final
- qty final
- decisión final

Esto permite:

- auditoría
- debugging
- análisis de desempeño
- aprendizaje futuro

---

# 14. Manejo de fallos

El sistema debe ser robusto ante:

- fallos de módulos
- errores de broker
- datos de mercado incompletos

Política general:


fail closed


Si el sistema no puede evaluar con seguridad, la operación no se ejecuta.

---

# 15. Relación con otros documentos

Este pipeline se basa en los siguientes documentos de arquitectura:


MODULE_DECISION_CONTRACT.md
KERNEL_ORCHESTRATION_MODEL.md
OPERATIONAL_MODULES_MODEL.md
MARKET_CONTEXT_MODULES_MODEL.md
LEARNING_MODULE_MODEL.md


Cada documento describe una parte del sistema.

---

# 16. Beneficios del pipeline modular

Este modelo permite:

- agregar nuevos módulos fácilmente
- soportar nuevos mercados
- mejorar estrategias sin reescribir el kernel
- mantener decisiones auditables
- operar capital propio con seguridad

---

# 17. Nota final

El kernel debe mantenerse como un **orquestador estable y modular**.

La evolución del sistema debe ocurrir principalmente mediante:

- nuevos módulos
- ajustes de políticas
- mejoras en aprendizaje

sin convertir el kernel en un sistema monolítico difícil de mantener.
