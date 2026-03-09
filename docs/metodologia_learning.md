# Metodologia Learning (M14)

## Objetivo

Definir una metodologia estable y auditable para que el modulo de Learning acompañe la decision de compra/ejecucion sin reemplazar las reglas base.

Principio operativo actual:
- Reglas/estrategia: `90%`
- Learning/modelo: `10%`

Esto mantiene un perfil conservador: el modelo ayuda a priorizar, pero no toma control total.

## Alcance funcional

El modulo Learning cubre:
1. Captura de decisiones (`learning_decision_snapshot`).
2. Etiquetado de resultados reales (`learning_decision_outcome`).
3. Consolidacion temporal en rollups (`learning_rollup_hourly`).
4. Exposicion de salud y experiencia para operacion:
   - `GET /ops/admin/learning/status`
   - `GET /ops/admin/learning/health`
   - `GET /ops/admin/learning/rollup`
   - `GET /ops/admin/learning/suggestion-report`

## Modelo de decision (scoring)

Formula de blend (conservadora):
- `score_final = rules_weight * score_base + model_weight * learning_score`

Configuracion por entorno:
- `LEARNING_DECISION_RULES_WEIGHT=0.9`
- `LEARNING_DECISION_MODEL_WEIGHT=0.1`
- `LEARNING_DECISION_MIN_SAMPLES=30`
- `LEARNING_DECISION_LOOKBACK_HOURS=720`
- `LEARNING_DECISION_MAX_DELTA_POINTS=6.0`

Interpretacion:
- `score_base`: resultado de reglas y controles de riesgo/liquidez.
- `learning_score`: señal estadistica del historial etiquetado.
- `learning_delta_points`: ajuste aplicado al score final.

## Metodologia temporal (horas-dias-semanas-meses-anos)

El endpoint `learning/health` reporta ventanas:
- `24h`
- `7d`
- `30d`
- `6m`
- `1y`

Por ventana calcula:
- decisiones y outcomes,
- pendientes/labeled/expired/no_price,
- tasas (`labeled_rate`, `expired_rate`, `no_price_rate`),
- `hit_rate` y `avg_return` (cuando hay outcomes etiquetados).

Objetivo de uso:
- `24h`: salud operativa inmediata.
- `7d` y `30d`: estabilidad tactica.
- `6m` y `1y`: memoria estadistica y tendencia estructural.

## Acumulacion y mantenimiento de experiencia

El modulo conserva experiencia por:
1. Snapshots de decisiones.
2. Outcomes etiquetados por horizonte.
3. Rollups por hora (para analitica/seguimiento).
4. Retencion configurable (TTL de raw y rollups).

Indicadores de experiencia (en `learning/health`):
- `snapshots_total`
- `outcomes_total`
- `labeled_total`
- `rollup_rows_total`
- `lifetime_days`
- primeras/ultimas marcas de actividad

## Indicador prediccion vs resultado real (Auto-pick)

En Auto-pick se expone:
- `predicted_hit_pct`
- `predicted_positive`
- `outcome_status`
- `realized_hit`
- `prediction_vs_real`:
  - `no_prediction`
  - `pending`
  - `match`
  - `mismatch`

Uso operativo:
- `pending`: decision aun no madura por horizonte.
- `match/mismatch`: medir si la prediccion coincide con el outcome real.

## Semaforo de salud (Learning Health)

Semaforo actual:
- `green`: pipeline estable.
- `yellow`: atencion (muestras bajas o calidad intermedia).
- `red`: calidad comprometida (por ejemplo, `expired/no_price` altos).

Recomendaciones automaticas:
- aumentar tasa de etiquetado,
- revisar fuente de precios,
- recalibrar reglas/modelo cuando baja `hit_rate` con muestra suficiente.

## Gobernanza de cambios

Reglas de control:
1. Cambios de pesos o umbrales solo por release controlado.
2. Todo cambio debe dejar evidencia en:
   - `docs/registro_operacion_diaria.md`
3. Validar con Integration Tests y Smoke antes de produccion.
4. Mantener reversibilidad por variables de entorno.

## Criterios de recalibracion sugeridos

Evaluar ajuste del modelo (no solo reglas) cuando:
1. `prediction_vs_real=mismatch` sostenido por encima de objetivo interno.
2. `hit_rate` cae con `labeled_total` suficiente.
3. `expired_rate` o `no_price_rate` deterioran calidad de dataset.

Acciones de recalibracion:
1. Corregir calidad de datos (label/price).
2. Ajustar horizonte y umbrales de labeling.
3. Ajustar pesos `rules/model` manteniendo enfoque conservador.

## Decision actual del proyecto

Estado adoptado:
- Metodologia definida y modelada por el equipo del proyecto.
- No es una caja negra externa.
- Mantiene un enfoque de riesgo conservador con trazabilidad y auditoria.
