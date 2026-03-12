# MARKET_PROFILES_MODEL.md

## 1. Propósito

Este documento define el modelo de **perfiles de mercado** que debe usar la plataforma.

El objetivo es permitir que el sistema opere sobre diferentes mercados y brokers sin romper el kernel central de trading.

La idea principal es:

- mantener un **kernel común**
- separar reglas específicas por mercado/broker
- evitar lógica dispersa y hardcoded en el motor principal

Este documento describe el modelo arquitectónico deseado para organizar:

- Binance / cripto
- IBKR / acciones e índices

---

## 2. Principio arquitectónico central

La plataforma no debe evolucionar hacia:

- un motor para cripto
- otro motor para acciones
- otro motor para índices

En cambio, debe evolucionar hacia:

```text
Trading Kernel
│
├── Market Profile: CRYPTO_BINANCE
└── Market Profile: EQUITIES_IBKR

Esto significa:

el pipeline de decisión es común

las reglas operativas son específicas por perfil

3. Qué pertenece al kernel común

Las siguientes responsabilidades deben permanecer en el núcleo común del sistema:

3.1 Ingesta de señales

recepción de señales

validación básica

scoping por tenant / usuario / cuenta

3.2 Pipeline pretrade

pretrade check

scan

auto-pick

scoring framework

selección de candidato

3.3 Guardrails del sistema

idempotencia

exposure checks

kill switch

audit logging

signal lifecycle

paper/live protection

3.4 Scheduler

ticks periódicos

loops por tenant

coordinación de ejecución

observabilidad del scheduler

3.5 Runtime de ejecución

interfaz común de dispatch

contratos de ejecución

trazabilidad

ciclo de vida de órdenes

Estas partes deben seguir siendo transversales al sistema.

4. Qué debe pertenecer a cada market profile

Cada perfil de mercado debe definir su propia política para:

4.1 Universe building

Cómo se construyen los candidatos de trading.

Ejemplos:

universo dinámico en cripto

universo más controlado en acciones

4.2 Reglas de liquidez

Cómo se interpreta:

spread

slippage

profundidad

condiciones mínimas de ejecución

4.3 Modelo de sizing

Cómo se determina:

qty base

multiplicadores

límites específicos

ajustes por side

4.4 Reglas de exposición

Cómo se mide riesgo operativo para ese mercado:

por símbolo

por asset class

por notional

por sesión

4.5 Reglas de ejecución

Cómo se envían órdenes:

normalización de cantidad

restricciones de precision

lot size

min notional

order types disponibles

4.6 Reglas de horario

Cómo se comporta el sistema según disponibilidad del mercado:

24/7 en cripto

sesiones de mercado en IBKR

feriados / cierres

premarket / after-hours si aplica

4.7 Reconciliación

Cómo se debe comparar el estado interno con el broker para ese mercado.

5. Perfil: CRYPTO_BINANCE

El perfil CRYPTO_BINANCE debe representar un mercado con estas características:

5.1 Naturaleza del mercado

mercado continuo

operación 24/7

universo amplio y cambiante

oportunidad más frecuente

alta sensibilidad a spread/slippage

5.2 Implicaciones para el motor

universe builder más dinámico

liquidez como factor dominante

sizing sensible a condiciones de mercado

mayor frecuencia de evaluación

mayor riesgo de repetición operativa por mercado siempre abierto

5.3 Responsabilidades específicas

construcción del universo cripto

normalización Binance

reglas de precision / step size / min notional

reglas de liquidez para auto-pick

reconciliación específica de órdenes y posiciones Binance

6. Perfil: EQUITIES_IBKR

El perfil EQUITIES_IBKR debe representar un mercado con estas características:

6.1 Naturaleza del mercado

mercado por sesiones

horarios definidos

instrumentos más estructurados

distinta semántica de órdenes

distinta disponibilidad de liquidez

6.2 Implicaciones para el motor

universe más controlado

reglas horarias importantes

mayor peso de exposición de portfolio

menor tolerancia a supuestos continuos tipo cripto

reconciliación distinta

6.3 Responsabilidades específicas

construcción de universo de acciones / índices

validación de sesión de mercado

sizing adaptado a acciones / índices

integración con bridge o fallback de IBKR

reconciliación específica IBKR

7. Qué NO debe pasar

Para mantener modularidad, deben evitarse estos errores:

7.1 No mezclar reglas específicas dentro del kernel

Evitar cosas como:

if broker == BINANCE en todas partes

if market == crypto dentro del núcleo de selección

hardcodes de mercado dispersos en ops.py

7.2 No asumir que ambos mercados comparten el mismo sizing

Cripto y acciones no tienen por qué compartir:

qty semilla

límites de liquidez

umbrales de ejecución

forma de exposición

7.3 No duplicar el pipeline completo

No crear:

un auto-pick completo para Binance

otro auto-pick completo para IBKR

Eso destruye mantenibilidad.

8. Estructura modular recomendada

La evolución ideal del sistema debería ir hacia algo como:

Trading Kernel
│
├── Candidate Selection
├── Pretrade Evaluation
├── Exposure Validation
├── Signal Lifecycle
├── Execution Dispatch Interface
├── Scheduler Coordination
└── Audit / Idempotency

y por debajo:

Market Profiles
│
├── CRYPTO_BINANCE
│   ├── universe policy
│   ├── liquidity policy
│   ├── sizing policy
│   ├── execution policy
│   └── reconciliation policy
│
└── EQUITIES_IBKR
    ├── universe policy
    ├── session policy
    ├── sizing policy
    ├── execution policy
    └── reconciliation policy
9. Aplicación al estado actual del sistema

Hoy el sistema ya tiene una parte del camino hecho:

Ya existe

kernel común de auto-pick

execution runtime separado

broker adapters separados

pipeline compartido de pretrade

guardrails generales

scheduler multi-tenant

Aún falta formalizar

perfiles explícitos por mercado

separación clara de sizing por perfil

separación clara de universe building por perfil

reglas horarias explícitas para IBKR

políticas de reconciliación por perfil

10. Beneficios del modelo

Este enfoque aporta:

10.1 Seguridad

Reduce errores de mezclar reglas de mercados distintos.

10.2 Mantenibilidad

Permite cambiar Binance sin romper IBKR.

10.3 Escalabilidad

Facilita agregar nuevos perfiles más adelante.

10.4 Claridad

Permite entender qué es común y qué es específico.

10.5 Evolución del SaaS

Hace posible que la futura plataforma multiusuario crezca sin dañar el kernel.

11. Regla de diseño recomendada

Cada nueva regla del sistema debe clasificarse en una de estas dos categorías:

A. Regla del kernel

Aplica a todo el sistema.

Ejemplos:

idempotencia

signal lifecycle

audit logging

exposure framework

scheduler locking

B. Regla del perfil de mercado

Aplica solo a un mercado/broker.

Ejemplos:

qty base de Binance

horarios de IBKR

precision rules

lógica de liquidez específica

ejecución y reconciliación por broker

Si una regla no puede clasificarse claramente, el diseño aún no está suficientemente modular.

12. Nota final

La modularidad en esta plataforma no debe verse como una optimización futura.

Debe verse como una decisión fundamental del diseño.

La plataforma quiere servir para:

operar capital propio primero

evolucionar a SaaS después

Ese objetivo solo es sostenible si existe:

un kernel estable

perfiles de mercado separados

reglas explícitas

bajo acoplamiento entre broker y motor central.
