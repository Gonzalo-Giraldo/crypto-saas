SIZING_MODEL.md
Modelo Actual de Sizing de Órdenes

Este documento describe cómo se calcula actualmente el tamaño de las órdenes (quantity sizing) dentro del sistema de trading.

Este documento no propone cambios, solamente documenta el comportamiento real observado en el código actual.

El objetivo es:

hacer el sistema auditable

permitir que futuros cambios sean controlados

evitar modificaciones accidentales en una parte crítica del trading engine

1. Resumen del modelo actual

El tamaño final de una orden se calcula aproximadamente como:

selected_qty =
    candidate.qty
    × liquidity_multiplier
    × sell_adjustment

Donde:

Componente	Descripción
candidate.qty	Cantidad base proveniente del universo de candidatos
liquidity_multiplier	Ajuste basado en condiciones de liquidez del mercado
sell_adjustment	Reducción adicional aplicada a posiciones SELL
2. Cantidad base (candidate.qty)

La cantidad base se genera en:

_build_auto_pick_universe(...)

ubicado en:

apps/api/app/api/ops.py

Valores típicos por broker:

Broker	Cantidad base
Binance	0.01
IBKR	1.0

Estas cantidades no están basadas en capital disponible, sino que funcionan como valores semilla para generar candidatos.

Las cantidades de entrada son validadas mediante:

PretradeCheckRequest.validate_qty

con límites definidos por:

RISK_INPUT_MAX_QTY
3. Ajuste por liquidez

Después de seleccionar un candidato, el sistema clasifica la liquidez del mercado mediante:

_classify_liquidity_state(...)

ubicado en:

apps/api/app/api/ops.py

La clasificación utiliza:

spread

slippage

score del candidato

límites definidos en runtime_policy

Resultados posibles:

Estado	Multiplicador
green	1.0
gray	0.5
red	0.0

Interpretación:

Estado	Comportamiento
green	posición completa permitida
gray	tamaño reducido a la mitad
red	candidato rechazado

Los umbrales actuales usan reglas relativas a:

spread <= 0.8 * max_spread
slippage <= 0.8 * max_slippage
score >= min_score + 2
4. Ajuste para SELL

En el proceso de auto-pick se aplica una regla adicional cuando el lado seleccionado es SELL.

Ubicación:

_auto_pick_from_scan(...)

Archivo:

apps/api/app/api/ops.py

Regla aplicada:

selected_qty = selected_qty * 0.35

Esto significa que las posiciones SELL utilizan 35% del tamaño equivalente de una posición BUY.

Esta regla se encuentra hardcoded en el código y actualmente no está parametrizada.

5. Validación de exposición

Antes de ejecutar una operación se ejecuta una validación de exposición mediante:

assert_exposure_limits(...)

ubicado en:

apps/api/app/services/trading_controls.py

La validación revisa:

posiciones abiertas

exposición por símbolo

exposición total por exchange

Detalle importante:

La validación de exposición utiliza:

candidate.qty

mientras que la ejecución real usa:

selected_qty

Esto introduce una ligera diferencia entre la cantidad validada y la cantidad finalmente ejecutada.

6. Normalización por broker

Antes de enviar la orden al broker, la cantidad se normaliza para cumplir con las reglas del exchange.

Ejemplo en Binance:

prepare_binance_market_order_quantity(...)

Este paso ajusta:

step size

cantidad mínima

notional mínimo

precisión

Esto garantiza que el broker acepte la orden.

7. Relación con balances de cuenta

El modelo actual de sizing no calcula el tamaño de la orden usando el balance disponible en la cuenta.

En su lugar, el sistema controla el riesgo mediante:

límites de exposición

número máximo de posiciones

límites por símbolo

límites por exchange

Los balances reales del broker pueden consultarse, pero no forman parte directa del cálculo del tamaño de la orden.

8. Reglas hardcoded actuales

El sistema contiene varias reglas implementadas directamente en código.

Ejemplos:

Regla	Ubicación
SELL × 0.35	_auto_pick_from_scan
multiplicadores 1.0 / 0.5 / 0.0	_classify_liquidity_state
ratio 0.8 para spread	_classify_liquidity_state
qty inicial 0.01 / 1.0	_build_auto_pick_universe

Estas reglas representan heurísticas operativas más que políticas explícitas configurables.

9. Observaciones arquitectónicas

El modelo actual de sizing parece haber evolucionado de manera incremental.

Características observadas:

mezcla de heurísticas y configuraciones

múltiples puntos de decisión

lógica distribuida en varias funciones

ausencia de un modelo centralizado de sizing

El sistema funciona operativamente, pero el comportamiento completo requiere entender varias capas de lógica.

10. Riesgos arquitectónicos identificados

Los principales riesgos asociados al modelo actual son:

Ajustes hardcoded

Reglas críticas como el ajuste de SELL están codificadas directamente en el código.

Diferencia entre validación y ejecución

La validación usa candidate.qty, mientras que la ejecución usa selected_qty.

Modelo de liquidez simplificado

El uso de tres estados discretos puede no reflejar adecuadamente condiciones reales del mercado.

Origen de la cantidad base

Las cantidades iniciales provienen de defaults del universo y no de un cálculo basado en capital.

Falta de una política centralizada

El sizing está distribuido entre varias funciones en lugar de existir una política única.

11. Propósito de este documento

Este documento existe para:

documentar el comportamiento actual

permitir auditorías futuras

facilitar refactorizaciones seguras

evitar cambios accidentales en el motor de trading

Cualquier modificación en la lógica de sizing debe reflejarse también en este documento.
