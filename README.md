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

🚀 Crypto SaaS
📌 Overview

Crypto SaaS es un motor backend para ejecución y gestión de señales de trading con control de riesgo diario integrado.

El sistema permite:

Crear señales de trading

Ejecutar posiciones

Cerrar posiciones con cálculo de PnL

Aplicar reglas estrictas de riesgo diario

Persistir estado en base de datos

Bloquear operaciones cuando se exceden límites

Este proyecto representa la base de un SaaS multiusuario para trading automatizado.

🏗 Architecture
apps/
 └── api/
      ├── models/
      ├── services/
      ├── routes/
      └── db/

Stack actual:

Python

FastAPI

SQLAlchemy

SQLite

Git Flow simplificado

🛡 Risk Engine

El sistema implementa control de riesgo diario persistente mediante:

Tabla: daily_risk_state

Campos clave:

trades_today

realized_pnl_today

daily_stop

max_trades

Reglas:

❌ Bloqueo si trades_today >= max_trades

❌ Bloqueo si realized_pnl_today <= daily_stop

✅ Reseteo automático por día (UTC)

📡 API Endpoints principales

POST /signals

POST /positions/open

POST /positions/close

GET /positions/risk/today

⚙️ Local Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.app.main:app --reload

Base de datos:

db.sqlite
🧠 Current Version

v1.0.0

Incluye:

Risk engine funcional

Persistencia estable

UTC safe timestamps

Arquitectura organizada

Versionado profesional

🗺 Roadmap
v1.1

Multi-asset support robusto

Mejor cálculo de fees

Logging estructurado

v1.2

Dockerización

Configuración por entorno

Tests automáticos

v2.0

Multiusuario real con autenticación

Dashboard web

Integración con exchange real

👨‍💻 Author

Gonzalo Giraldo
Founder – Crypto SaaS
