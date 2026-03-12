# ARCHITECTURE_INDEX.md

## 1. Propósito

Este documento organiza la documentación arquitectónica del sistema de trading.

La plataforma está diseñada como un **sistema modular de decisiones**, donde un kernel central orquesta módulos especializados que analizan mercado, riesgo, ejecución y aprendizaje.

Este índice permite navegar rápidamente por todos los componentes del sistema.

---

# 2. Documentos principales de arquitectura

## Núcleo del sistema

### Trading Decision Engine
docs/TRADING_DECISION_ENGINE.md

Describe el funcionamiento del motor de decisiones del sistema, incluyendo:

- auto-pick
- pipeline de decisión
- scoring
- flujo desde señal hasta ejecución
- integración con módulos operativos

---

### Module Decision Contract
docs/MODULE_DECISION_CONTRACT.md

Define el **contrato homogéneo de comunicación entre módulos**.

Este documento es la base de la arquitectura modular.

Define:

- `ModuleContext`
- `ModuleDecision`
- campos estándar
- reglas de agregación
- reason codes

Permite que el kernel sea gobernado por variables y módulos intercambiables.

---

### Market Profiles Model
docs/MARKET_PROFILES_MODEL.md

Define cómo el sistema adapta su comportamiento según el tipo de mercado.

Incluye perfiles como:

- crypto
- equities
- indices

Cada perfil puede influir en:

- reglas de trading
- sizing
- sesiones de mercado
- restricciones del broker

---

# 3. Seguridad operativa

### Trading Safety Checklist
docs/TRADING_SAFETY_CHECKLIST.md

Checklist de seguridad para validar que el sistema cumple con:

- idempotencia
- protección contra órdenes duplicadas
- validación de exposición
- separación paper/live
- protección contra fallos de broker

Este documento es usado antes de activar trading en producción.

---

# 4. Preparación para producción

### Production Readiness
docs/PRODUCTION_READINESS.md

Lista de requisitos para que el sistema pueda operar con capital real.

Incluye:

- verificación de módulos críticos
- validación de ejecución con brokers
- controles de riesgo
- monitoreo y auditoría
- condiciones mínimas de estabilidad

---

# 5. Roadmap del sistema

### Trading Roadmap
docs/TRADING_ROADMAP.md

Define la evolución planeada del sistema.

Incluye:

- fases de desarrollo
- mejoras arquitectónicas
- expansión de módulos
- incorporación de nuevos mercados
- evolución hacia SaaS

---

# 6. Módulos principales del kernel

El kernel de trading consulta múltiples módulos que aportan decisiones parciales.

Ejemplos de módulos:

## Decisión operativa
- buy / no buy
- sell / no sell
- sizing
- liquidez
- balances / activos
- exposición / riesgo

## Contexto de mercado
- tendencia de mercado
- régimen de mercado
- estado del mercado

## Inteligencia adaptativa
- módulo de aprendizaje
- feedback de desempeño
- degradación de patrones

En el futuro pueden agregarse módulos como:

- noticias macro
- noticias por activo
- eventos corporativos
- análisis de sentimiento

Todos los módulos deben cumplir el contrato definido en:

docs/MODULE_DECISION_CONTRACT.md

---

# 7. Filosofía del sistema

El sistema está diseñado bajo los siguientes principios:

- modularidad
- decisiones explicables
- defensas en capas
- seguridad primero
- kernel orquestador
- evolución basada en módulos

El objetivo es construir un motor capaz de:

- operar capital propio con seguridad
- evolucionar gradualmente hacia una plataforma SaaS

---

# 8. Uso de esta documentación

Para entender el sistema se recomienda el siguiente orden de lectura:

1. MODULE_DECISION_CONTRACT.md  
2. TRADING_DECISION_ENGINE.md  
3. MARKET_PROFILES_MODEL.md  
4. TRADING_SAFETY_CHECKLIST.md  
5. PRODUCTION_READINESS.md  
6. TRADING_ROADMAP.md
