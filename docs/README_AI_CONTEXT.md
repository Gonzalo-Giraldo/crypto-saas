README_AI_CONTEXT.md
# AI Context Guide for the Trading Platform

Este documento organiza **el contexto arquitectónico del proyecto** para que tanto desarrolladores como agentes de IA puedan entender rápidamente cómo funciona el sistema.

Este archivo define **el orden recomendado de lectura** de la documentación técnica.

---

# 1. Propósito de este documento

El sistema es una **plataforma de trading automatizado multi-tenant y multi-broker**.

La lógica del sistema incluye:

- ingestión de señales
- selección automática de operaciones
- cálculo de tamaño de órdenes
- controles de riesgo
- ejecución en brokers
- auditoría y monitoreo

Debido a la complejidad del dominio, el sistema está documentado en múltiples archivos especializados.

Este documento explica **cómo recorrer esa documentación correctamente**.

---

# 2. Orden recomendado de lectura

## Paso 1 — Identidad del proyecto

Leer primero:


AGENTS.md


Este documento define:

- reglas operativas del sistema
- restricciones del proyecto
- modelo multi-tenant
- brokers soportados
- pipeline general
- módulos protegidos

Es el documento que establece **cómo deben comportarse los agentes de desarrollo**.

---

## Paso 2 — Arquitectura general

Leer:


docs/ARCHITECTURE.md


Describe:

- estructura del backend
- capas del sistema
- scheduler multi-tenant
- separación de brokers
- organización de servicios

Este documento explica **la estructura del sistema**.

---

## Paso 3 — Motor de trading

Leer:


docs/TRADING_ENGINE.md


Explica:

- cómo se procesa una señal
- cómo se ejecuta el pipeline de trading
- cómo se conectan los componentes operativos

Este documento describe **el flujo de trading a alto nivel**.

---

## Paso 4 — Modelo de riesgo

Leer:


docs/RISK_MODEL.md


Define:

- filosofía de riesgo
- chequeos pre-trade
- separación paper/live
- idempotencia
- exposición
- protección contra duplicados

Este documento describe **las reglas de seguridad del sistema**.

---

## Paso 5 — Modelo de sizing

Leer:


docs/SIZING_MODEL.md


Explica cómo se calcula el tamaño de una orden.

Incluye:

- origen de `qty`
- multiplicadores de liquidez
- ajuste SELL
- normalización por broker
- limitaciones actuales del modelo

Este documento describe **cómo se calcula la cantidad de cada operación**.

---

## Paso 6 — Modelo de decisión

Leer:


docs/TRADING_DECISION_MODEL.md


Describe:

- cómo se selecciona un candidato
- cómo se decide BUY o SELL
- cómo se aplican filtros de liquidez
- cómo se selecciona el activo final

Este documento describe **la lógica de decisión del sistema**.

---

## Paso 7 — Guardas de riesgo

Leer:


docs/TRADING_RISK_GUARDS.md


Describe las defensas del sistema:

- exposición
- idempotencia
- separación paper/live
- scheduler safety
- protección contra duplicados
- ejecución en broker

Este documento explica **qué protege al sistema contra errores y fallas operativas**.

---

# 3. Archivos críticos del sistema

Los siguientes archivos contienen la lógica central del trading engine:


apps/api/app/api/ops.py
apps/api/app/services/trading_controls.py
apps/api/app/services/risk_engine.py
apps/api/app/api/positions.py
apps/api/app/api/signals.py
apps/api/app/main.py
apps/worker/app/engine/execution_runtime.py
apps/worker/app/engine/binance_client.py
apps/worker/app/engine/ibkr_client.py


Estos archivos deben tratarse como **módulos protegidos**.

Cambios en ellos pueden afectar directamente:

- decisiones de trading
- cálculo de riesgo
- ejecución en brokers
- estabilidad operativa

---

# 4. Pipeline simplificado del sistema

El flujo principal del sistema es:


Signal / Candidate
↓
Pretrade evaluation
↓
Candidate scan
↓
Auto-pick decision
↓
Sizing calculation
↓
Exposure validation
↓
Paper/live guards
↓
Broker execution
↓
Audit logging


Este pipeline está implementado principalmente en:


apps/api/app/api/ops.py


---

# 5. Objetivo de esta documentación

La documentación del sistema busca:

- hacer el sistema comprensible
- permitir auditorías técnicas
- evitar cambios accidentales en lógica crítica
- facilitar el trabajo de agentes de IA
- permitir evolución segura del motor de trading

---

# 6. Regla fundamental

Antes de modificar el motor de trading se deben revisar:


docs/SIZING_MODEL.md
docs/TRADING_DECISION_MODEL.md
docs/TRADING_RISK_GUARDS.md


Estos documentos explican el comportamiento operativo actual.

---

# 7. Contexto del proyecto

Estado actual del proyecto:

- sistema desarrollado aproximadamente al **85%**
- motor de trading funcional
- integración con **BINANCE** y **IBKR**
- arquitectura **multi-tenant**
- ejecución automática basada en señales
- soporte para **paper trading y live trading protegido**

El foco actual es:

- estabilización del sistema
- documentación del comportamiento
- reducción de riesgos operativos
- preparación para producción controlada

---

# 8. Uso por agentes de IA

Los agentes de desarrollo deben:

1. Leer este documento.
2. Seguir el orden de lectura recomendado.
3. Entender el comportamiento actual antes de proponer cambios.
4. Evitar modificar módulos protegidos sin análisis previo.

---

# 9. Mantenimiento de la documentación

Cada vez que cambie alguno de estos componentes:

- lógica de decisión
- sizing
- controles de riesgo
- ejecución en brokers

debe actualizarse también la documentación correspondiente.

La documentación es parte del sistema.
