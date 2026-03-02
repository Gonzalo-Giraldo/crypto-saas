# Matriz Regimen de Mercado (Binance vs IBKR)

Fecha base: 2026-03-02  
Objetivo: separar politicas de trading por `exchange + estrategia + regimen` para conservar capital y filtrar ejecuciones de baja calidad.

## Regimenes
- `bull`: tendencia favorable y volatilidad controlada.
- `bear`: tendencia adversa / mayor riesgo de whipsaw.
- `range`: mercado lateral (se exige mayor selectividad).

## SWING_V1 - BINANCE
| Variable | Bull | Bear | Range |
|---|---:|---:|---:|
| allow_regime | true | true | false |
| rr_min | 1.5 | 1.6 | 1.9 |
| min_volume_24h_usdt | 50,000,000 | 70,000,000 | 90,000,000 |
| max_spread_bps | 10 | 8 | 7 |
| max_slippage_bps | 15 | 12 | 10 |
| max_hold_minutes | 720 | 480 | 360 |
| max_abs_funding_rate_bps* | 20 | 15 | 12 |

\* guard operativo aplicado por motor pretrade.

## SWING_V1 - IBKR
| Variable | Bull | Bear | Range |
|---|---:|---:|---:|
| allow_regime | true | true | false |
| rr_min | 1.4 | 1.5 | 1.8 |
| max_spread_bps | 12 | 10 | 8 |
| max_slippage_bps | 15 | 12 | 10 |
| max_hold_minutes | 720 | 480 | 360 |
| filtros obligatorios | in_rth=true | in_rth=true | in_rth=true |
| bloqueo de eventos | macro/earnings | macro/earnings | macro/earnings |

## INTRADAY_V1 - BINANCE
| Variable | Bull | Bear | Range |
|---|---:|---:|---:|
| allow_regime | true | true | false |
| rr_min | 1.3 | 1.4 | 1.6 |
| min_volume_24h_usdt | 80,000,000 | 100,000,000 | 120,000,000 |
| max_spread_bps | 8 | 7 | 6 |
| max_slippage_bps | 12 | 10 | 8 |
| max_hold_minutes | 240 | 180 | 120 |
| max_abs_funding_rate_bps* | 20 | 15 | 12 |

## INTRADAY_V1 - IBKR
| Variable | Bull | Bear | Range |
|---|---:|---:|---:|
| allow_regime | true | true | false |
| rr_min | 1.3 | 1.4 | 1.6 |
| max_spread_bps | 10 | 8 | 6 |
| max_slippage_bps | 12 | 10 | 8 |
| max_hold_minutes | 240 | 180 | 120 |
| filtros obligatorios | in_rth=true | in_rth=true | in_rth=true |
| bloqueo de eventos | macro/earnings | macro/earnings | macro/earnings |

## Reglas transversales recomendadas
- `leverage <= max_leverage` (perfil de riesgo).
- `symbol_allowlist` por exchange (opcional, recomendado).
- Crypto: bloquear `crypto_event_block=true`.
- Crypto `OFF_HOURS`: endurecer automaticamente liquidez/costos.

## Carga rapida via API (admin)
- Leer politicas actuales:
  - `GET /ops/admin/strategy-runtime-policies`
- Actualizar una politica:
  - `PUT /ops/admin/strategy-runtime-policies/{strategy_id}/{exchange}`

Payload ejemplo (SWING_V1/BINANCE):
```json
{
  "allow_bull": true,
  "allow_bear": true,
  "allow_range": false,
  "rr_min_bull": 1.5,
  "rr_min_bear": 1.6,
  "rr_min_range": 1.9,
  "min_volume_24h_usdt_bull": 50000000,
  "min_volume_24h_usdt_bear": 70000000,
  "min_volume_24h_usdt_range": 90000000,
  "max_spread_bps_bull": 10,
  "max_spread_bps_bear": 8,
  "max_spread_bps_range": 7,
  "max_slippage_bps_bull": 15,
  "max_slippage_bps_bear": 12,
  "max_slippage_bps_range": 10,
  "max_hold_minutes_bull": 720,
  "max_hold_minutes_bear": 480,
  "max_hold_minutes_range": 360
}
```
