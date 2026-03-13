# DOMAIN_CONSTANTS_AUDIT.md

## Inventario de hardcodes y constantes de dominio/negocio

Este documento registra el inventario de referencias y constantes de dominio detectadas en el código del sistema que podrían requerir normalización futura.

**Este inventario NO implica cambio inmediato.**  
Las acciones se decidirán después, por grupos, en el momento adecuado y bajo supervisión arquitectónica.

El objetivo es:
- dejar trazabilidad del análisis
- evitar que cambios futuros rompan comportamiento sin entender el contexto
- identificar qué puede consolidarse con trabajo mínimo vs qué requiere rediseño

---

# 1. Separación conceptual de términos

Antes de revisar el inventario, es necesario distinguir cuatro conceptos que el código actual mezcla implícitamente:

### Instrument / base asset

El activo que se compra o vende. En `BTCUSDT`, el base asset es `BTC`.  
La posición interna trackea este activo. Tiene precio pero no define de qué moneda proviene el capital.

### Quote asset del instrumento

El denominador de precio del par. En `BTCUSDT`, el quote asset es `USDT`.  
Es la moneda en la que se *expresa* el precio del instrumento — no necesariamente la moneda que el usuario tiene en su cuenta.

### Funding asset / buying currency / capital asset

La moneda que el usuario realmente gasta para ejecutar la compra.  
En Binance SPOT, si el usuario tiene `USDC` libre en cuenta, necesita el par `BTCUSDC`, no `BTCUSDT`.  
El funding asset está determinado por la composición real del balance de la cuenta, no por una constante de sistema.  
En IBKR, el equivalente es la moneda base del account (`USD`, `EUR`, `GBP`), configurada por el broker per-cuenta.

### Settlement / account / base currency

La moneda en la que el broker reporta PnL neto, liquidación y margen.  
En Binance puede ser USDT pero también USDC o BTC según el modo.  
En IBKR es la `base currency` del account, que en el fallback simulado del sistema está hardcodeada como `"USD"`.

Estos cuatro conceptos son distintos. El sistema actual los trata como si fueran el mismo en varios puntos del código.

---

# 2. Por qué `USDT` no debe modelarse como constante global de compra

1. **Alternativas stablecoin activas en Binance**: `USDC`, `FDUSD`, `TUSD` (parcialmente deprecado). Muchos usuarios migraron capital a USDC después del cierre de BUSD (2023-2024).

2. **El balance real puede ser cero USDT y positivo USDC**: si el código intenta comprar `BTCUSDT` pero el usuario tiene solo `USDC` libre, la orden falla por saldo insuficiente o Binance intenta una conversión silenciosa con slippage adicional.

3. **El guard existente (`get_binance_spot_usdt_free_for_user`) busca `asset != "USDT"` literalmente**: si el usuario tiene USDC como capital, reporta `usdt_free = None` y bloquea correctamente — pero con diagnóstico incorrecto y sin consultar el balance USDC real.

4. **Consistencia rota**: `AUTO_PICK_REAL_BINANCE_QUOTE` existe en `config.py` como fuente de verdad parcial, pero hay 4 puntos en el código que hardcodean `"USDT"` independientemente sin leer esa config.

---

# 3. Por qué `BTCUSDT` y símbolos similares no deben modelarse como constantes globales de compra

`BTCUSDT` combina dos variables independientes: el instrumento (`BTC`) y el quote de ese instrumento en la cuenta (`USDT`).

1. **La lista `_binance_fallback_symbols()`** hardcodea `["BTCUSDT","ETHUSDT",...]` como símbolos de emergencia. Si el sistema se configura para operar con USDC, esta lista envía símbolos inválidos al broker.

2. **El símbolo no define el capital disponible**: una posición long BTC con capital USDC es la misma posición que con capital USDT, pero requiere un símbolo diferente y un balance fuente diferente.

3. **No es trasladable entre brokers**: en IBKR no existe un par `BTCUSD` equivalente al spot de Binance. La misma lógica `símbolo = instrumento + quote` no es portable.

4. **Riesgo de validación**: si se permite operar un símbolo `BTCUSDC` en el futuro, `_is_binance_directional_symbol` lo rechazaría porque asume `USDT` como único quote válido.

---

# 4. Inventario estructurado — BINANCE (Textual / T)

| ID | Archivo | Fragmento | Cat | Qué modela hoy | Por qué existe | Riesgo si se deja |
|----|---------|-----------|-----|----------------|----------------|-------------------|
| T1 | `apps/api/app/services/trading_controls.py:17` | `endswith("USDT") or "/USDT"` en `infer_exchange_from_symbol()` | **C** | Heurística de routing: símbolo termina en USDT → Binance, else → IBKR | Regla histórica correcta para el modelo actual | Si se opera BTCUSDC, se enrutaría como IBKR; exposición contabilizada en exchange incorrecto |
| T2 | `apps/api/app/api/ops.py:554` | `not s.endswith("USDT")` en `_is_binance_directional_symbol()` | **B** | Filtra del universo todo símbolo que no sea USDT | Asume que el único quote válido es USDT | Si `AUTO_PICK_REAL_BINANCE_QUOTE` se cambia a USDC, el universo de scanning queda vacío silenciosamente |
| T3 | `apps/api/app/api/ops.py:556` | `banned_suffixes = ("UPUSDT","DOWNUSDT","BULLUSDT","BEARUSDT")` | **C** | Excluye tokens apalancados Binance | Lista correcta para el mercado actual con quote USDT | Con quote USDC, los equivalentes `UPUSDC` etc. no quedarían excluidos |
| T4 | `apps/api/app/api/ops.py:559-568` | `non_directional = {"USDCUSDT","BUSDUSDT","FDUSDUSDT",...}` | **C** | Excluye pares stablecoin-to-stablecoin del scanning | Correcto conceptualmente | Con quote USDC, los pares equivalentes no quedarían excluidos; la lógica entera colapsa con cambio de quote |
| T5 | `apps/api/app/api/ops.py:541-548` | `_binance_fallback_symbols()` → `["BTCUSDT","ETHUSDT",...]` | **C** | Lista de símbolos de emergencia cuando el ticker feed falla | Hardcodea instrumento + quote completo | Con quote USDC configurado, el fallback enviaría símbolos inválidos al broker |
| T6 | `apps/api/app/api/ops.py:~2609` | `guard_symbol.endswith("USDT") or "/USDT"` en broker guard | **B** | Determina si el broker-side USDT guard aplica | Escrito para la realidad actual (USDT es el quote) | Con quote USDC, el guard no se activaría; capital USDC no sería validado pre-dispatch |
| T7 | `apps/worker/app/engine/execution_runtime.py:665` | `if asset != "USDT": continue` en `get_binance_spot_usdt_free_for_user` | **B** | Extrae balance libre de USDT de la cuenta Binance | Asume que el único capital de compra es USDT | Con capital en USDC: guard devuelve `usdt_free=None` y bloquea correctamente pero con diagnóstico incorrecto y nombre de función incorrecto |

---

# 5. Inventario estructurado — IBKR (Textual / T)

| ID | Archivo | Fragmento | Cat | Qué modela hoy | Por qué existe | Riesgo si se deja |
|----|---------|-----------|-----|----------------|----------------|-------------------|
| T8 | `apps/worker/app/engine/ibkr_client.py:129` | `"currency": "USD"` en fallback simulado | **D** | Reporta USD como moneda de cuenta cuando el bridge IBKR no está configurado | Simplificación para modo simulado/paper | Si un usuario tiene EUR o GBP como base currency real, el fallback simula USD; cálculos de notional serían numéricamente incorrectos |

---

# 6. Inventario estructurado — Config / Compartido (Textual / T)

| ID | Archivo | Fragmento | Cat | Qué modela hoy | Por qué existe | Riesgo si se deja |
|----|---------|-----------|-----|----------------|----------------|-------------------|
| T9 | `apps/api/app/core/config.py:50` | `AUTO_PICK_REAL_BINANCE_QUOTE: str = "USDT"` | **A** | Fuente parcial de verdad para el quote de Binance en real guard | Diseñado para gobernar el guard de quote | Está bien gobernada, pero solo la lee `_auto_pick_real_guard_reason`; los puntos T2, T6, T7 no la leen |
| T10 | `apps/api/app/core/config.py:97` | `DEFAULT_CAPITAL_BASE_USD: float = 10000.0` | **D** | Capital base de referencia en USD | Valor semilla para contextos que no usen balance real | El nombre implica USD; actualmente no se usa en sizing activo (qty base es 0.01 seed), pero cualquier uso futuro heredaría la asunción USD |

---

# 7. Inventario estructurado — BINANCE (Numérico / N)

| ID | Archivo | Fragmento | Cat | Qué modela hoy | Por qué existe | Riesgo si se deja |
|----|---------|-----------|-----|----------------|----------------|-------------------|
| N1 | `apps/api/app/api/ops.py:1697-1700` | `0.80 ×` max_spread/slippage en `_classify_liquidity_state()` | **C** | Threshold de green: condición de "margen cómodo" (20% headroom) respecto al límite máximo | Heurística operativa documentada | No configurable; cambio de condiciones de mercado puede volverlo demasiado o poco restrictivo |
| N2 | `apps/api/app/api/ops.py:1702` | `min_score_pct + 2.0` en green threshold | **C** | Score debe superar el mínimo por margen de 2 puntos para clasificar como green | Requiere ventaja clara antes de asignar liquidez completa | Hardcoded; debería ser parámetro junto con multiplicadores de liquidez |
| N3 | `apps/api/app/api/ops.py:1706` | `0.5` multiplicador gray | **C** | Reduce qty a 50% en condiciones de liquidez aceptables | Regla conservadora documentada en `SIZING_MODEL.md` | Impacto directo en tamaño de orden live; no configurable |
| N4 | `apps/api/app/api/ops.py:1709` | `0.0` multiplicador red | **C** | Rechaza candidato en condiciones de liquidez insuficiente | Fallo-cerrado correcto | No se puede cambiar sin código |
| N5 | `apps/api/app/api/ops.py:2399` | `* 0.35` SELL size reduction | **C** | Posiciones SELL usan 35% del tamaño equivalente BUY | Conservadurismo para posiciones cortas; documentado en `SIZING_MODEL.md` | No configurable; si la estrategia cambia, requiere cambio de código |
| N6 | `apps/api/app/api/ops.py:~2626` | `* 1.02` buffer en broker guard USDT | **B** | Requiere 2% de USDT adicional sobre el notional estimado | Buffer para precio drift entre estimación y ejecución | No configurable; el 2% puede ser insuficiente en alta volatilidad intra-tick |
| N7 | `apps/api/app/api/ops.py:574` | `10_000_000.0` volume floor | **C** | Filtra símbolos con volumen < $10M/24h del universo de scanning | Define qué es "suficientemente líquido para ser considerado" | Hardcoded; umbral no responde a condiciones de mercado cambiantes |
| N8 | `apps/api/app/api/ops.py:941,1007,1589` | `/ 200_000_000.0` normalización de volumen (aparece 3 veces) | **C** | Normaliza volume 24h a escala [0,1] donde $200M = liquidez máxima | $200M como referencia de "volumen alto" en cripto | 3 apariciones independientes no coordinadas; all hardcoded |
| N9 | `apps/api/app/api/ops.py:945-946` | `max(3.0, 14.0 - (10.0*liq))` y `max(5.0, 18.0-12.0*liq)` | **C** | Calcula spread/slippage estimados dinámicamente desde volumen en universe builder | Modelo simplificado: a mayor liquidez, menor spread estimado | Rango hardcoded (3-14 bps spread, 5-18 bps slippage); puede no reflejar condiciones actuales |
| N10 | `apps/api/app/api/ops.py:952` | `qty=0.01` Binance seed qty | **C** | Cantidad base de candidatos Binance | Cantidad mínima operativa típica; no basada en capital disponible | Documentado en `SIZING_MODEL.md`; puede ser inadecuada para distintos usuarios |
| N11 | `apps/api/app/api/ops.py:1592-1604` | Score market: `45.0` base + coeficientes `16, 14, 4, 7, 10, 0.6, 0.55, 1.5` | **C** | Calcula `score_market` de cada candidato pre-trade | Modelo calibrado empíricamente | Completamente hardcoded; 10+ coeficientes sin documentación de origen ni backtesting visible |
| N12 | `apps/api/app/api/ops.py:1589` | `liq = min(1.0, vol_24h / 200_000_000.0)` dentro del scoring | **C** | Contribución de liquidez al score market | Mismo anchor $200M del universe builder | Aparece independiente de N8; deberían estar coordinados |
| N13 | `apps/api/app/api/ops.py:1590` | `atr_pct - 6.0` ATR penalty threshold en scoring | **C** | ATR > 6% genera penalización creciente en el score | Asume que >6% ATR es "excesivamente volátil" | Válido en cripto high-vol pero debería ser configurable por broker/par |
| N14 | `apps/api/app/api/ops.py:1593` | `micro_mult = 0.6 if atr > 6.0 else 1.0` | **C** | Reduce peso de señal 15m en alta volatilidad | Señal de corto plazo menos confiable en mercados erráticos | Transición discreta en umbral de 6.0 en vez de gradual |
| N15 | `apps/api/app/api/ops.py:778-784` | MTF weights `(0.55, 0.30, 0.15)` y `(0.60, 0.40)` | **C** | Pondera timeframes para `trend_score` y `momentum_score` | Modelo de señal multi-timeframe calibrado | Hardcoded; no configurable |
| N16 | `apps/api/app/api/ops.py:778` | Normalizadores `(0.03, 0.02, 0.01, 0.015)` en `_norm_return` | **C** | Normaliza retornos relativos; calibrados al rango típico de movimiento cripto | Usados en `_compute_binance_mtf_signal` | No documentadas; cambio de clase de activo los haría inválidos |
| N17 | `apps/api/app/api/ops.py:815-816` | micro weights `(0.5, 0.3, 0.2)` y divisor `/ 0.012` | **C** | Construye señal micro 15m ponderada y normalizada | Divisor normaliza al rango [-1,1] | Origen del `0.012` no documentado; el más opaco del inventario |
| N18 | `apps/api/app/api/ops.py:399` | `>= 50.0` threshold para `predicted_positive` | **C** | Clasificación binaria: positivo si probabilidad ≥ 50% | Threshold natural de probabilidad | Si el modelo tiene sesgo sistemático, 50% no es el threshold correcto |
| N19 | `apps/api/app/api/ops.py:498` | `max(0.5, ...)` hard floor sobre RR en exit plan | **C** | Garantiza RR mínimo absoluto de 0.5 independientemente del config | Fallback de seguridad | El config `AUTO_PICK_REAL_EXIT_PLAN_MIN_RR` puede estar configurado por debajo de 0.5 sin efecto y sin advertencia |
| N20 | `apps/api/app/api/ops.py:533` | `max(5, ...)` hard floor sobre max_hold_minutes en exit plan | **C** | Garantiza hold mínimo de 5 minutos | Evita planes de salida instantáneos | Mismo problema que N19: config tiene efecto limitado si se configura más bajo que el floor |
| N21 | `apps/api/app/api/ops.py:1571` | `score_weight_rules=0.4, score_weight_market=0.6` defaults en `_pretrade_scores()` | **C** | Ponderación rules vs market en el score final pre-trade; market pesa más | Calibración histórica | No gobernado por settings (a diferencia de los pesos de learning); hardcoded como defaults de función |

---

# 8. Inventario estructurado — IBKR (Numérico / N)

| ID | Archivo | Fragmento | Cat | Qué modela hoy | Por qué existe | Riesgo si se deja |
|----|---------|-----------|-----|----------------|----------------|-------------------|
| N22 | `apps/api/app/services/decision_engine.py:21` | `max(min_score_pct + 4.0, 85.0)` para SELL threshold | **C** | El threshold de score para SELL es mínimo + 4 puntos con floor absoluto de 85 | Conservadurismo extra para posiciones cortas | El floor de 85 es independiente del `min_score_pct` configurado; si se configura `min_score_pct=90`, el SELL threshold sería 94 (correcto), pero si se configura con min bajo, el floor puede sorprender al operador |
| N23 | `apps/api/app/api/ops.py:882-888` | Tuples `(trend, momentum, atr, spread_bps, slippage_bps)` por símbolo IBKR | **C** | Estima métricas de mercado para cada acción IBKR sin feed real | Fallback estático cuando no hay feed de mercado IBKR | Valores estáticos nunca se actualizan con condiciones reales; inadecuados en earnings week o eventos macro |
| N24 | `apps/api/app/api/ops.py:~907` | `rr_estimate=1.6` seed IBKR en scan | **C** | RR semilla para candidatos IBKR en el scan | Valor razonable como default | No tiene base en condiciones actuales del instrumento |
| N25 | `apps/api/app/api/ops.py:1026` | `qty=1.0` seed IBKR | **C** | Cantidad semilla para candidatos IBKR (vs 0.01 de Binance) | Cantidad mínima típica para acciones | Documentado; no es capital-based |

---

# 9. Los 4 puntos B de consolidación simple

Estos cuatro puntos son los de menor riesgo y mayor alineación con la config existente. No requieren cambio de modelo; solo requieren leer `AUTO_PICK_REAL_BINANCE_QUOTE` (ya disponible en `config.py`) en vez de usar `"USDT"` literal.

| ID | Archivo | Acción futura mínima |
|----|---------|----------------------|
| **T2** | `ops.py:_is_binance_directional_symbol()` | Reemplazar `endswith("USDT")` con `endswith(settings.AUTO_PICK_REAL_BINANCE_QUOTE.upper())` |
| **T6** | `ops.py:~2609` broker guard eligibility | Reemplazar `endswith("USDT") or "/USDT"` con el quote de config |
| **T7** | `execution_runtime.py:665` en `get_binance_spot_usdt_free_for_user` | Reemplazar `asset != "USDT"` con el quote de config; considerar renombrar la función |
| **N6** | `ops.py:~2626` buffer `* 1.02` | Agregar `AUTO_PICK_REAL_BINANCE_BROKER_GUARD_BUFFER: float = 1.02` a config y referenciarla |

**Estos cambios están identificados pero NO están aprobados ni planificados todavía.**  
Se decidirán en el momento adecuado como un grupo coherente y con pruebas correspondientes.

---

# 10. Puntos C/D que requieren modelo nuevo o revisión posterior

Estos puntos no pueden resolverse con sustitución de config. Requieren diseño explícito previo.

| ID | Problema | Razón para no tocar todavía |
|----|----------|----------------------------|
| **T1** | `infer_exchange_from_symbol` mezcla routing de exchange con quote del instrumento | Requiere tabla de routing explícita o mapeo broker→quote_assets |
| **T4** | `non_directional` lista asume USDT como quote | Requiere generación dinámica desde el quote configurado o lista por-quote |
| **T5** | `_binance_fallback_symbols()` lista completa símbolos | Requiere separar lista de base assets de la construcción del símbolo final |
| **T8** | IBKR fallback currency `"USD"` | Requiere campo `account_currency` en `ExchangeSecret` o bridge real |
| **T10** | `DEFAULT_CAPITAL_BASE_USD` nombre y valor | Solo importa si se implementa capital-based sizing; actualmente no afecta ejecución |

---

# 11. Constantes numéricas que requieren justificación prioritaria

Estas constantes gobiernan el comportamiento de selección y sizing. No requieren cambio inmediato, pero deben ser documentadas con justificación de su origen antes de que alguien las modifique sin entender su efecto.

| ID | Constante | Justificación pendiente |
|----|-----------|------------------------|
| **N11** | `45.0` base + coeficientes `16, 14, 4, 7, 10, 0.6, 0.55, 1.5` en score market | ¿Cómo se calibraron? ¿Cuándo fue la última validación empírica? |
| **N15** | MTF weights `(0.55, 0.30, 0.15)` | ¿Hay backtesting que respalde este weighting de timeframes? |
| **N1**  | `0.80 ×` spread/slippage para green | ¿Qué tan sensible es la tasa de ejecución a cambiar 0.80 a 0.75 o 0.85? |
| **N13** | `6.0` ATR threshold en scoring | ¿6% era el ATR típico en el momento de calibración? |
| **N17** | `/ 0.012` divisor micro 15m | Origen completamente opaco; no documentado en ningún otro doc |
| **N22** | `85.0` floor SELL score | ¿Por qué 85 y no 80 o 90? Interacción con `min_score_pct` no documentada explícitamente |
| **N5**  | `0.35` SELL size reduction | Documentado en `SIZING_MODEL.md` pero sin justificación de por qué 35% y no 25% o 50% |
| **N23** | Tuples IBKR `(0.20, 0.12, 1.8, 6.0, 8.0)` etc. | ¿Basados en datos históricos? ¿Fecha de calibración? |

---

# 12. Resumen de categorías de acción futura

| Categoría | Descripción | Puntos identificados | Decisión |
|-----------|-------------|----------------------|----------|
| **A** | Ya gobernado correctamente por config | T9 | Sin acción necesaria |
| **B** | Consolidación simple con config existente | T2, T6, T7, N6 | Acción futura de bajo riesgo, en grupo, cuando se decida |
| **C** | Regla válida hoy, hardcoded, por revisar en contexto | T1, T3, T4, T5, N1-N5, N7-N21, N24, N25 | Requieren justificación antes de cambiar; ningún cambio inmediato |
| **D** | Requiere modelo per-cuenta/broker/región | T8, T10 | No tocar sin diseño explícito previo |

---

# 13. Principio de acción futura

Cuando llegue el momento de actuar sobre alguno de estos puntos, los pasos obligatorios son:

1. Confirmar que el punto pertenece al grupo a trabajar en esa sesión (no mezclar B con C, no mezclar textual con numérico)
2. Para B: verificar que el cambio es mecánico y que las pruebas cubren el caso
3. Para C numérico: documentar el origen y la calibración *antes* de proponer cambio
4. Para D: no proceder sin un diseño del modelo destino aprobado

Este documento se actualizará cuando se ejecute alguna acción sobre estos puntos.
