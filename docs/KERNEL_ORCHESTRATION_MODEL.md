docs/KERNEL_ORCHESTRATION_MODEL.md

y pega exactamente esto.

# KERNEL_ORCHESTRATION_MODEL.md

## 1. Propósito

Este documento define cómo funciona el **kernel de orquestación** del sistema de trading.

El kernel no debe ser entendido como un lugar donde vive toda la lógica de negocio mezclada.  
Debe ser entendido como:

- el coordinador del pipeline de decisión
- el consumidor de decisiones de módulos homogéneos
- el agregador de resultados
- el responsable de producir la decisión final auditable

Este documento describe cómo el kernel debe:

- recibir contexto
- consultar módulos
- agregar resultados
- resolver conflictos
- decidir si una operación continúa o se bloquea

---

## 2. Principio arquitectónico central

El kernel debe funcionar como un **director de orquesta**.

Eso significa que:

- no debe contener toda la lógica específica de cada mercado o producto
- no debe depender de reglas dispersas y hardcoded
- no debe decidir en aislamiento
- debe coordinar módulos especializados que devuelven decisiones homogéneas

El kernel debe leer:

```text
ModuleContext

y consumir múltiples:

ModuleDecision

para producir una:

FinalTradingDecision
3. Posición del kernel dentro del sistema

El kernel se ubica conceptualmente entre:

Entrada

señales

candidatos

contexto de mercado

contexto de riesgo

estado operativo

Salida

decisión final de operar o no operar

side aprobado

qty aprobada

guardias activas

rastro de auditoría

Flujo conceptual:

Signal / Candidate
        ↓
ModuleContext
        ↓
Kernel Orchestrator
        ↓
Operational Modules
Market Context Modules
Adaptive Modules
Hard Safety Modules
        ↓
Decision Aggregation
        ↓
FinalTradingDecision
        ↓
Execution Layer
4. Responsabilidades del kernel

El kernel debe ser responsable de:

4.1 Orquestación

Llamar módulos en el orden correcto.

4.2 Agregación

Recibir y combinar respuestas homogéneas.

4.3 Resolución de conflictos

Resolver qué decisión prevalece cuando los módulos discrepan.

4.4 Producción de decisión final

Emitir una decisión final única y auditable.

4.5 Trazabilidad

Registrar qué módulos participaron, qué dijeron y por qué se tomó la decisión final.

5. Qué NO debe hacer el kernel

Para evitar convertirse en un monolito, el kernel no debe:

contener lógica específica de Binance o IBKR mezclada

contener reglas dispersas de mercado

ejecutar órdenes directamente

mutar estado crítico sin pasar por capas autorizadas

esconder valores mágicos no trazables

reemplazar a los módulos en sus responsabilidades especializadas

6. Entrada al kernel: ModuleContext

El kernel recibe un contexto unificado del caso actual.

Ese contexto representa:

la oportunidad de trading

el entorno de ejecución

el estado operativo

el perfil de mercado

el riesgo actual

el estado de la señal/candidato

Este contexto debe ser suficientemente rico para que los módulos no dependan de lecturas opacas o acoplamiento excesivo.

El contrato está definido en:

docs/MODULE_DECISION_CONTRACT.md
7. Categorías de módulos consultados por el kernel

El kernel debe consultar módulos por familias.

7.1 Módulos de seguridad dura

Son prioritarios y no negociables.

Ejemplos:

tenant safety

idempotencia

paper/live protection

signal lifecycle

exposure hard limits

Estos módulos pueden bloquear directamente la operación.

7.2 Módulos de decisión operativa

Toman decisiones directas sobre la viabilidad de la operación.

Ejemplos:

buy / no buy

sell / no sell

sizing

liquidez

balances / activos

exposición

sesión / horario

7.3 Módulos de contexto de mercado

Aportan contexto adicional para enriquecer la decisión.

Ejemplos:

tendencia de mercado

market regime

market state

más adelante noticias o eventos

7.4 Módulos de inteligencia adaptativa

Aportan aprendizaje y feedback.

Ejemplos:

learning

confidence adjustment

degradation detection

historical pattern quality

8. Orden lógico de orquestación

El kernel debe consultar módulos en una secuencia razonable.

Orden sugerido:

Etapa 1 — Validaciones duras iniciales

tenant safety

signal lifecycle

paper/live invariants

idempotencia

session viability básica

Etapa 2 — Contexto de mercado

market trend

market regime

market state

Etapa 3 — Evaluación operativa

buy / no buy

sell / no sell

liquidez

balances / activos

exposición preliminar

Etapa 4 — Inteligencia adaptativa

aprendizaje

confidence adjustment

pattern degradation

Etapa 5 — Sizing

qty base

multiplicadores

overrides

restricciones específicas

Etapa 6 — Resolución final

agregación de score

aplicación de vetos

qty final

decisión final

Este orden puede ajustarse, pero debe mantenerse explícito y documentado.

9. Agregación de decisiones

El kernel no debe simplemente “sumar cosas”.
Debe aplicar reglas claras.

9.1 Regla de veto

Si un módulo de seguridad dura devuelve:

block_trade = true

el kernel debe tratarlo como un veto fuerte, salvo política explícita distinta.

9.2 Regla de score

Los módulos que aportan score_delta pueden modificar el score del candidato.

El kernel debe producir:

final_score = base_score + sum(score_delta)

si esa es la política vigente.

9.3 Regla de cantidad

Los módulos de sizing y riesgo pueden aportar:

qty_multiplier

qty_override

El kernel debe tener una política explícita para resolver cuál prevalece.

Ejemplo conceptual:

partir de candidate_qty

aplicar multiplicadores

aplicar override si un módulo autorizado lo define

validar qty final

9.4 Regla de prioridad

Si dos módulos entran en conflicto, el kernel debe aplicar prioridad.

Jerarquía sugerida:

hard safety
> exposure / session
> sizing
> market context
> learning

Esto significa, por ejemplo:

exposición vencida gana sobre aprendizaje optimista

mercado cerrado gana sobre buen score

paper/live invariant gana sobre cualquier oportunidad

10. Resolución de conflictos

Cuando los módulos no coinciden, el kernel debe resolver sin ambigüedad.

Ejemplos:

Caso 1

módulo de tendencia: PASS, score +4

módulo de exposición: FAIL, block_trade true

Resultado:

la operación se bloquea

Caso 2

módulo de liquidez: WARN, qty_multiplier 0.5

módulo de aprendizaje: PASS, score +2

módulo de sizing: PASS, qty_override específico

Resultado:

el kernel debe aplicar la política de prioridad y decidir si el override está permitido

Caso 3

módulo de sesión: FAIL, market closed

módulo de score: PASS, score alto

Resultado:

la operación se rechaza

11. Salida del kernel: FinalTradingDecision

El kernel debe producir una salida final homogénea.

Propuesta conceptual:

FinalTradingDecision
- decision_id
- decision_status
- allow_trade
- block_trade
- approved_side
- approved_qty
- final_score
- applied_modules
- blocking_modules
- reason_codes
- audit_payload
- execution_ready
Significado de campos importantes

decision_status: PASS / WARN / FAIL

allow_trade: indica si puede continuar

block_trade: indica veto final

approved_side: BUY / SELL / NONE

approved_qty: qty final aprobada

applied_modules: lista de módulos considerados

blocking_modules: módulos que vetaron

reason_codes: motivos de la decisión final

execution_ready: indica si pasa a capa de ejecución

12. Auditoría del kernel

El kernel debe dejar registro explícito de:

qué contexto recibió

qué módulos consultó

qué devolvió cada módulo

cómo resolvió conflictos

por qué decidió operar o no operar

qué qty final aprobó

qué score final aprobó

Esto es esencial para:

auditoría

debugging

investigación de incidentes

explicación a futuro

análisis del módulo de aprendizaje

13. Relación entre kernel y market profiles

El kernel es común.
No debe multiplicarse por mercado.

Los perfiles de mercado deben influir a través de módulos especializados.

Ejemplo:

Caso BTC / Binance

El kernel consulta módulos configurados para CRYPTO_BINANCE.

Caso acción / IBKR

El kernel consulta módulos configurados para EQUITIES_IBKR.

Esto permite:

un kernel estable

perfiles variables

reglas específicas sin contaminar el núcleo

La relación con perfiles está definida en:

docs/MARKET_PROFILES_MODEL.md
14. Relación entre kernel y módulo de aprendizaje

El módulo de aprendizaje no debe reemplazar al kernel.

Debe:

aportar ajuste

aportar evidencia

modular score o qty si la política lo permite

nunca derrotar guardas de seguridad dura

El aprendizaje puede influir, pero no debe tener autoridad absoluta sobre:

tenant safety

paper/live invariants

exposure hard blocks

signal lifecycle integrity

15. Kernel gobernado por variables

El diseño del kernel debe favorecer que muchas mejoras futuras se hagan mediante:

parámetros

thresholds

pesos

multiplicadores

prioridades

políticas de agregación

y no mediante:

if/else dispersos

valores mágicos embebidos

reglas escondidas en múltiples funciones

Esto permite que el sistema evolucione con menor intervención de código central.

16. Invariantes no negociables

Aunque el kernel sea flexible, ciertas cosas no deben quedar sujetas a interpretación modular blanda.

No negociable:

tenant isolation

idempotencia crítica

signal lifecycle válido

paper/live separation

audit logging

invariantes de ejecución segura

Estos elementos deben seguir siendo límites absolutos del sistema.

17. Beneficios del modelo de orquestación

Este modelo aporta:

17.1 Claridad

El kernel deja de ser una caja negra.

17.2 Modularidad real

Se pueden agregar módulos sin romper el diseño.

17.3 Escalabilidad

Se pueden soportar más mercados y productos.

17.4 Auditabilidad

Se puede reconstruir por qué se tomó una decisión.

17.5 Gobernanza

Permite dirigir la evolución del sistema con reglas explícitas.

18. Preguntas obligatorias antes de agregar un módulo nuevo

Antes de agregar cualquier módulo nuevo, deben responderse estas preguntas:

¿En qué etapa del kernel participa?

¿Qué lee del ModuleContext?

¿Qué devuelve en ModuleDecision?

¿Puede bloquear?

¿Puede modificar score?

¿Puede modificar qty?

¿Qué prioridad tiene?

¿Qué reason_codes aporta?

¿Cómo impacta la trazabilidad?

¿Puede entrar en conflicto con otro módulo?

Si estas respuestas no están claras, el módulo aún no está listo.

19. Nota final

El kernel de esta plataforma no debe evolucionar como una función cada vez más grande.

Debe evolucionar como:

un orquestador estable

gobernado por contratos

alimentado por módulos homogéneos

controlado por políticas explícitas

capaz de operar capital propio primero y SaaS después

Ese es el fundamento de una arquitectura robusta y sostenible.
