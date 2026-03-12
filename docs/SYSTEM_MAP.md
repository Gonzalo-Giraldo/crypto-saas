# SYSTEM_MAP.md

## 1. Propósito

Este documento ofrece un **mapa integral del sistema**.

Su objetivo es permitir que una persona o un agente de IA entienda rápidamente:

- qué componentes existen
- cómo se conectan
- cuál es el kernel
- qué módulos participan en la decisión
- cómo fluye una señal hasta una orden
- dónde están los principales riesgos

Este documento funciona como **vista de conjunto** del sistema.

---

## 2. Visión general

La plataforma es un sistema de trading:

- multi-tenant
- multiusuario
- multi-broker
- orientado primero a operar capital propio
- con evolución futura hacia SaaS

Brokers actuales:

- BINANCE
- IBKR

Perfil de mercados actual:

- crypto
- acciones / índices

---

## 3. Estructura general del sistema

```text
Tenant / User / Account
          ↓
      Signal Layer
          ↓
   Candidate Construction
          ↓
      Trading Kernel
          ↓
  Decision / Risk / Context Modules
          ↓
 FinalTradingDecision
          ↓
   Execution Validation
          ↓
   Broker Execution Layer
          ↓
  Audit / Learning / Monitoring
4. Capas del sistema
4.1 Capa de entrada

Responsable de:

recibir señales

recibir candidatos

validar requests

asegurar scoping de tenant/user/account

Archivos típicos:

apps/api/app/api/signals.py

apps/api/app/api/ops.py

apps/api/app/api/positions.py

4.2 Capa de kernel

Responsable de:

construir el contexto unificado

consultar módulos

agregar decisiones

producir la decisión final

Documentos clave:

docs/MODULE_DECISION_CONTRACT.md

docs/KERNEL_ORCHESTRATION_MODEL.md

docs/KERNEL_EXECUTION_PIPELINE.md

docs/KERNEL_VARIABLES_AND_POLICIES.md

4.3 Capa de módulos

Responsable de aportar decisiones parciales.

Familias:

Módulos operativos

buy / no buy

sell / no sell

liquidity

exposure

balance

session

sizing

Módulos de contexto de mercado

market trend

market regime

market state

noticias futuras

Módulos de inteligencia adaptativa

learning

confidence adjustment

degradation detection

Documentos clave:

docs/OPERATIONAL_MODULES_MODEL.md

docs/MARKET_CONTEXT_MODULES_MODEL.md

docs/LEARNING_MODULE_MODEL.md

4.4 Capa de ejecución

Responsable de:

validar guardias finales

preparar la orden

normalizar cantidad

enviar a broker

registrar resultado

Archivos típicos:

apps/worker/app/engine/execution_runtime.py

apps/worker/app/engine/binance_client.py

apps/worker/app/engine/ibkr_client.py

4.5 Capa de riesgo y guardas

Responsable de:

exposición

límites

idempotencia

kill switch

paper/live

seguridad de scheduler

protección contra duplicados

Documentos clave:

docs/RISK_MODEL.md

docs/TRADING_RISK_GUARDS.md

docs/TRADING_SAFETY_CHECKLIST.md

docs/PRODUCTION_READINESS.md

4.6 Capa de scheduler y automatización

Responsable de:

ticks automáticos

market monitor

auto-pick

exit logic

learning pipeline

Archivo principal:

apps/api/app/main.py

Documento clave:

docs/SCHEDULER_AND_CONCURRENCY_MODEL.md

5. Kernel central

El kernel debe entenderse como:

orquestador

agregador

coordinador

productor de la decisión final

No debe ser entendido como:

un contenedor monolítico de toda la lógica

un lugar donde se mezclan reglas de todos los mercados

El kernel consume:

ModuleContext

y agrega múltiples:

ModuleDecision

para producir:

FinalTradingDecision
6. Contrato común del sistema

Todos los módulos del sistema deben hablar el mismo idioma.

Entrada común

ModuleContext

Salida común

ModuleDecision

Esto permite:

modularidad real

extensibilidad

auditabilidad

incorporación futura de nuevos módulos y productos

Documento clave:

docs/MODULE_DECISION_CONTRACT.md

7. Flujo principal de trading
Signal / Candidate
        ↓
ModuleContext
        ↓
Market Context Modules
        ↓
Operational Modules
        ↓
Learning Module
        ↓
Sizing / Exposure / Validation
        ↓
FinalTradingDecision
        ↓
Execution Guards
        ↓
Broker Execution
        ↓
Audit + Learning Feedback
8. Market profiles

El sistema debe evolucionar como:

Trading Kernel
│
├── CRYPTO_BINANCE
└── EQUITIES_IBKR

El kernel es común.

Lo específico por mercado debe vivir en perfiles y módulos especializados.

Documento clave:

docs/MARKET_PROFILES_MODEL.md

9. Módulos más sensibles del sistema

Archivos más críticos:

apps/api/app/api/ops.py

apps/api/app/main.py

apps/api/app/api/deps.py

apps/api/app/routes/auth.py

apps/api/app/services/trading_controls.py

apps/api/app/services/risk_engine.py

apps/api/app/api/positions.py

apps/worker/app/engine/execution_runtime.py

apps/worker/app/engine/binance_client.py

apps/worker/app/engine/ibkr_client.py

Estos deben tratarse como módulos protegidos.

10. Riesgos más importantes identificados
Riesgos de ejecución

client_order_id no determinista

retries con posible duplicación

Riesgos de concurrencia

open_from_signal en paralelo

scheduler vs manual

exposición calculada sobre estado snapshot

Riesgos de diseño

sizing heurístico y parcialmente hardcoded

exposure check vs qty final no perfectamente alineados

reglas mezcladas en el núcleo actual

Riesgos operativos

reconciliación incompleta con broker

dry_run sin idempotencia obligatoria en algunas rutas

SQLite sin locking fuerte

11. Estado actual del sistema

Fortalezas:

arquitectura clara

pipeline de trading funcional

multi-tenant

guardrails reales

paper/live protegido

scheduler con lock en Postgres

documentación extensa y estructurada

Debilidades:

hardening pendiente

kernel todavía con partes centralizadas

duplicación/concurrencia no totalmente blindadas

sizing no totalmente formalizado como política unificada

Estado global:

Condicionalmente listo para producción conservadora
12. Prioridades actuales

Prioridades técnicas principales:

idempotencia real a nivel broker

lock de señal / posición

alinear exposure con qty final

reconciliación broker

consolidar kernel modular gobernado por variables

Prioridad estratégica:

operar primero capital propio

madurar el kernel

evolucionar a SaaS después

13. Relación entre documentos

Orden sugerido de lectura:

docs/ARCHITECTURE_INDEX.md

docs/SYSTEM_MAP.md

docs/MODULE_DECISION_CONTRACT.md

docs/KERNEL_ORCHESTRATION_MODEL.md

docs/KERNEL_EXECUTION_PIPELINE.md

docs/OPERATIONAL_MODULES_MODEL.md

docs/MARKET_CONTEXT_MODULES_MODEL.md

docs/LEARNING_MODULE_MODEL.md

docs/MARKET_PROFILES_MODEL.md

documentos de riesgo y operación

14. Nota final

Este mapa existe para que el sistema pueda entenderse rápido, mantenerse ordenado y evolucionar sin perder coherencia.

La intención es que cualquier persona o agente pueda usar este documento como punto de entrada principal al sistema.
