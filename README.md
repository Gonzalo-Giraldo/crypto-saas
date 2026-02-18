# crypto-saas

SaaS privado (2 usuarios) para trading spot en Binance con enfoque en control de riesgo y transparencia.

## Estructura
- apps/api: FastAPI (endpoints + ops)
- apps/worker: tareas (scanner/ejecución/reconciliación/snapshots)
- docs: decisiones, reglas, runbook
- scripts: utilidades

## Fase 1
- MICRO_LIVE 350 USDT
- BTC/ETH
- Riesgo por trade: 1.25 USDT
- Daily stop: 5 USDT
- 1 posición, 3 trades/día

