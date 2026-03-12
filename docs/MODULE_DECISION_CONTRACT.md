# MODULE_DECISION_CONTRACT.md

## 1. Propósito

Este documento define el **contrato homogéneo de interacción entre el kernel de trading y sus módulos operativos**.

Su objetivo es que cualquier módulo del sistema:

- reciba un contexto común
- devuelva una respuesta homogénea
- pueda agregarse, reemplazarse o ajustarse sin romper el kernel

Este contrato es la base para una arquitectura modular donde el kernel funciona como **orquestador de decisiones**.

---

## 2. Principio central

Todos los módulos del sistema deben **hablar el mismo idioma**.

Eso significa que:

- todos reciben una estructura de entrada compatible
- todos devuelven una estructura de salida compatible
- el kernel no depende de implementaciones internas
- el kernel solo interpreta resultados homogéneos

Este principio permite:

- agregar nuevos módulos en el futuro
- cambiar reglas sin reescribir el kernel
- introducir nuevos productos, mercados o brokers
- mejorar el sistema mediante variables y políticas

---

## 3. Alcance del contrato

Este contrato aplica a módulos como:

- buy / no buy
- sell / no sell
- sizing
- liquidez
- balances / activos
- exposición / riesgo
- sesión / horario
- tendencia de mercado
- aprendizaje
- contexto de mercado futuro (por ejemplo noticias)

No reemplaza las defensas duras del sistema, como:

- idempotencia
- tenant isolation
- paper/live separation
- signal lifecycle
- audit logging

Esas siguen siendo invariantes del kernel.

---

## 4. Entrada estándar: `ModuleContext`

Todo módulo debe recibir una estructura conceptual común llamada:

```text
ModuleContext

Esta estructura representa el estado actual de una oportunidad de trading.

4.1 Campos mínimos recomendados
Identidad y contexto del sistema

tenant_id

user_id

account_id

broker

market_profile

environment_mode (paper / live)

timestamp

Contexto del activo

symbol

asset_type

side

price

market_state

market_regime

trend_state

Contexto de señal / candidato

signal_id

candidate_id

signal_source

candidate_score

candidate_qty

candidate_metadata

Contexto de riesgo / exposición

open_positions_count

open_qty_symbol

open_notional_exchange

daily_risk_state

risk_profile

runtime_policy

Contexto de ejecución

dry_run

idempotency_key

broker_constraints

execution_capabilities

Contexto de auditoría

request_id

trace_id

decision_cycle_id

5. Regla de entrada

Todos los módulos deben asumir que ModuleContext es:

válido

trazable

auditable

enriquecible

Los módulos pueden leer contexto, pero no deben mutarlo arbitrariamente.

Si un módulo necesita aportar nueva información, debe hacerlo mediante su salida, no alterando el contexto base de forma opaca.

6. Salida estándar: ModuleDecision

Todo módulo debe devolver una estructura homogénea llamada:

ModuleDecision

Esta es la “llave única” del sistema.

El kernel solo debe necesitar interpretar este contrato.

7. Campos de ModuleDecision
7.1 Identidad del módulo

module_id

module_type

module_version

7.2 Estado del dictamen

decision_status

allow_trade

block_trade

requires_review

Valores sugeridos para decision_status:

PASS

WARN

FAIL

INFO

7.3 Efecto sobre la decisión

score_delta

risk_delta

qty_multiplier

qty_override

priority_weight

7.4 Motivos y evidencia

reason_codes

summary

evidence

notes

7.5 Variables de salida

output_variables

Este campo permite que un módulo entregue variables adicionales para uso del kernel o de otros módulos.

Ejemplos:

liquidity_state = gray

trend_bias = bullish

learning_confidence = low

session_open = false

8. Significado de los campos principales
allow_trade

Indica si el módulo aprueba continuar.

block_trade

Indica si el módulo exige detener la operación.

Regla:

si block_trade = true, el kernel debe tratarlo como veto duro o veto fuerte según política

score_delta

Permite sumar o restar score al candidato.

qty_multiplier

Permite ajustar la cantidad sin redefinirla completamente.

qty_override

Permite reemplazar la cantidad final cuando el módulo tenga autoridad explícita para hacerlo.

reason_codes

Lista estructurada de motivos, no texto libre solamente.

9. Códigos de razón (reason_codes)

Los módulos deben producir códigos estandarizados.

Ejemplos:

Liquidez

LIQUIDITY_GREEN

LIQUIDITY_GRAY

LIQUIDITY_RED

Riesgo / exposición

EXPOSURE_LIMIT_REACHED

SYMBOL_QTY_LIMIT_REACHED

DAILY_RISK_LIMIT_REACHED

Sesión / mercado

MARKET_CLOSED

SESSION_RESTRICTED

SYMBOL_NOT_ELIGIBLE

Tendencia

TREND_BULLISH

TREND_BEARISH

TREND_UNCLEAR

TREND_CONFLICT

Aprendizaje

LEARNING_CONFIDENCE_HIGH

LEARNING_CONFIDENCE_LOW

LEARNING_REGIME_BLOCK

LEARNING_PATTERN_DEGRADED

Ejecución

BROKER_CONSTRAINT_BLOCK

MIN_NOTIONAL_NOT_MET

PRECISION_ADJUSTMENT_REQUIRED

Estos códigos deben ser:

consistentes

auditables

reutilizables

comprensibles por humanos y máquinas

10. Tipos de módulo (module_type)

Para mantener orden, cada módulo debe pertenecer a una familia.

10.1 Módulos de seguridad dura

No negociables:

idempotencia

paper/live

tenant safety

signal lifecycle

10.2 Módulos de decisión operativa

buy / no buy

sell / no sell

sizing

liquidez

balances

exposición

sesión

10.3 Módulos de contexto de mercado

tendencia de mercado

market regime

state classification

más adelante noticias o eventos

10.4 Módulos de inteligencia adaptativa

aprendizaje

performance feedback

confidence adjustment

degradation detection

11. Reglas del kernel al consumir ModuleDecision

El kernel debe comportarse como orquestador, no como contenedor de toda la lógica.

El kernel debe:

recibir múltiples ModuleDecision

agregarlas

resolver conflictos

calcular decisión final

registrar trazabilidad

El kernel no debe depender de:

lógica interna del módulo

implementación específica

valores mágicos dispersos

12. Reglas de agregación sugeridas
12.1 Veto duro

Si un módulo devuelve:

block_trade = true

el kernel puede detener la operación inmediatamente según política.

12.2 Ajuste acumulativo

Los campos como:

score_delta

risk_delta

qty_multiplier

pueden agregarse mediante reglas explícitas.

12.3 Prioridad

Si dos módulos entran en conflicto, el kernel debe resolverlo según:

prioridad del módulo

tipo del módulo

política de agregación

Por ejemplo:

seguridad dura > aprendizaje

exposición > tendencia

sesión cerrada > score alto

13. Ejemplo conceptual de salida
Ejemplo 1 — módulo de liquidez
module_id: liquidity
module_type: operational
decision_status: WARN
allow_trade: true
block_trade: false
score_delta: -2
qty_multiplier: 0.5
reason_codes:
- LIQUIDITY_GRAY
output_variables:
  liquidity_state: gray
Ejemplo 2 — módulo de tendencia
module_id: market_trend
module_type: market_context
decision_status: PASS
allow_trade: true
block_trade: false
score_delta: 4
reason_codes:
- TREND_BULLISH
output_variables:
  trend_bias: bullish
Ejemplo 3 — módulo de aprendizaje
module_id: learning
module_type: adaptive_intelligence
decision_status: WARN
allow_trade: true
block_trade: false
score_delta: -6
qty_multiplier: 0.7
reason_codes:
- LEARNING_PATTERN_DEGRADED
output_variables:
  learning_confidence: low
Ejemplo 4 — módulo de exposición
module_id: exposure
module_type: hard_safety
decision_status: FAIL
allow_trade: false
block_trade: true
reason_codes:
- EXPOSURE_LIMIT_REACHED
output_variables:
  projected_notional: 125000
14. Reglas de diseño para los módulos

Todo módulo debe ser:

explicable

auditable

desacoplado

reversible

predecible

Todo módulo debe evitar:

mutar estado crítico sin autorización del kernel

ejecutar órdenes directamente

saltarse guardas de seguridad dura

producir resultados ambiguos

15. Qué permite este contrato

Este contrato permite que, en el futuro, puedan agregarse módulos nuevos como:

noticias por activo

noticias macro

eventos corporativos

nuevos productos

nuevos mercados

nuevos brokers

nuevos clasificadores de riesgo

nuevas fuentes de aprendizaje

sin rediseñar el kernel completo.

16. Regla clave de evolución

Antes de agregar un nuevo módulo al sistema, deben responderse estas preguntas:

¿Qué lee del ModuleContext?

¿Qué devuelve en ModuleDecision?

¿Puede bloquear?

¿Puede modificar score?

¿Puede modificar qty?

¿Qué prioridad tiene?

¿Qué reason_codes usa?

Si estas respuestas no están claras, el módulo aún no está listo para integrarse.

17. Nota final

La modularidad real del sistema no depende solo de separar archivos o carpetas.

Depende de que todos los módulos usen:

un contexto común

una salida homogénea

una semántica consistente

Este contrato es la base para que el kernel de trading evolucione hacia un sistema:

modular

gobernable por variables

extensible

auditable

apto para capital propio primero y SaaS después
