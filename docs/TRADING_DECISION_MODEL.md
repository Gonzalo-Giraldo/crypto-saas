TRADING_DECISION_MODEL.md
Modelo de decisión del motor de trading

Este documento describe cómo el sistema decide ejecutar una operación de trading.

No propone cambios ni mejoras.
Describe el comportamiento actual del código.

Este documento complementa:

docs/ARCHITECTURE.md
docs/TRADING_ENGINE.md
docs/RISK_MODEL.md
docs/SIZING_MODEL.md

Su objetivo es explicar claramente:

cómo se selecciona un candidato

cómo se decide BUY o SELL

cómo se aplican controles de riesgo

cómo se envía una orden al broker

1. Pipeline completo de decisión

El flujo completo desde una señal hasta una orden sigue estas etapas:

Signal / Candidate
        ↓
Pretrade evaluation
        ↓
Candidate scan
        ↓
Auto-pick selection
        ↓
Sizing calculation
        ↓
Exposure validation
        ↓
Paper/live guards
        ↓
Broker execution runtime

Las funciones principales involucradas están en:

apps/api/app/api/ops.py
2. Ingreso de señales o candidatos

Las señales pueden entrar al sistema mediante:

Señales manuales
POST /signals
GET /signals
POST /signals/claim

Archivo principal:

apps/api/app/api/signals.py
Endpoints de pretrade

Para análisis y selección automática:

Binance

POST /ops/execution/pretrade/binance/check
POST /ops/execution/pretrade/binance/scan
POST /ops/execution/pretrade/binance/auto-pick

IBKR

POST /ops/execution/pretrade/ibkr/check
POST /ops/execution/pretrade/ibkr/scan
POST /ops/execution/pretrade/ibkr/auto-pick

Archivo principal:

apps/api/app/api/ops.py
3. Evaluación pretrade

Cada candidato pasa por una evaluación inicial:

_evaluate_pretrade_for_user(...)

Esta función aplica múltiples controles:

validación de estrategia

validación de timeframe

validación de régimen de mercado

validación de riesgo diario

validación de configuración del usuario

validación de exposición inicial

Resultado:

El candidato se marca como válido o inválido para continuar en el pipeline.

4. Escaneo de candidatos

Los candidatos válidos pasan a:

_scan_pretrade_candidates(...)

Esta etapa:

evalúa múltiples candidatos

ejecuta verificaciones adicionales

prepara una lista de activos elegibles

Cada candidato mantiene atributos como:

symbol

side

score

spread

slippage

qty base

5. Selección automática (auto-pick)

La selección final ocurre en:

_auto_pick_from_scan(...)

Archivo:

apps/api/app/api/ops.py

Este es el punto central de decisión del sistema.

La función:

ordena los candidatos por score

aplica filtros de liquidez

aplica reglas por lado (BUY/SELL)

selecciona el candidato con mejor score elegible

Variables clave:

selected_score
selected_side
liquidity_state
runtime_policy thresholds
6. Decisión BUY vs SELL

El lado de la operación proviene de:

candidate.side

La lógica de selección respeta condiciones adicionales.

Ejemplo:

SELL solo permitido si liquidity_state == green

BUY puede ejecutarse incluso con liquidez gray.

Esto introduce un sesgo conservador hacia posiciones SELL.

7. Clasificación de liquidez

La liquidez se calcula mediante:

_classify_liquidity_state(...)

Estados posibles:

Estado	Significado
green	liquidez excelente
gray	liquidez aceptable
red	liquidez insuficiente

Multiplicadores asociados:

Estado	Multiplicador
green	1.0
gray	0.5
red	0.0
8. Cálculo del tamaño de la orden

Una vez seleccionado el candidato se calcula el tamaño final.

Definido en:

_auto_pick_from_scan(...)

Fórmula aproximada:

selected_qty =
    candidate.qty
    × liquidity_multiplier

Si la operación es SELL:

selected_qty = selected_qty × 0.35

Detalles completos del sizing se documentan en:

docs/SIZING_MODEL.md
9. Validación de exposición

Antes de ejecutar la orden se valida exposición.

Función:

assert_exposure_limits(...)

Archivo:

apps/api/app/services/trading_controls.py

Esta validación revisa:

número de posiciones abiertas

exposición por símbolo

exposición total por exchange

10. Separación paper vs live

El sistema soporta:

Modo	Comportamiento
paper	simulación
live	ejecución real

Control principal:

dry_run flag

Si:

dry_run = true

la orden no se envía realmente.

Para ejecución real se requiere:

X-Idempotency-Key

y pasar guardias adicionales.

11. Ejecución en broker

El despacho final se realiza mediante:

execution_runtime

Archivo:

apps/worker/app/engine/execution_runtime.py

Funciones principales:

execute_binance_test_order_for_user(...)
execute_ibkr_test_order_for_user(...)

Antes del envío:

la cantidad se normaliza

se genera un client_order_id

se registra auditoría

12. Auditoría y registro

Cada decisión genera registros en:

AuditLog

Esto permite reconstruir:

qué candidato fue elegido

qué score tenía

qué liquidez se detectó

qué cantidad se envió

13. Propósito de este documento

Este documento existe para:

explicar cómo el sistema decide operar

permitir auditoría del comportamiento del motor

facilitar mantenimiento futuro

evitar cambios accidentales en la lógica de decisión

Este documento debe actualizarse si la lógica de decisión cambia.
