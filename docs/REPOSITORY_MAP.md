# REPOSITORY_MAP.md

## Purpose

This document provides a quick map of the repository structure.

It helps engineers and AI agents locate the most important parts of the system quickly.

For architectural rules see:
- AGENTS.md
- docs/ARCHITECTURE.md
- docs/TRADING_ENGINE.md
- docs/RISK_MODEL.md

---

# Root Structure

crypto-saas
│
├─ AGENTS.md
├─ docs
├─ apps
├─ scripts
├─ tests
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
└─ render.yaml


---

# Main Application Code

apps/


Contains all application logic.

### API

apps/api/app/


Contains:

- REST API endpoints
- services
- models
- runtime logic
- scheduler lifecycle

Important folders:

apps/api/app/api/
apps/api/app/services/
apps/api/app/models/
apps/api/app/core/


---

# Core Operational Files

### Trading execution core

apps/api/app/api/ops.py


Coordinates:

- pretrade checks
- auto-pick flows
- signal-driven execution
- order preparation

---

### Scheduler and runtime lifecycle

apps/api/app/main.py


Handles:

- application startup
- scheduler loop
- tenant orchestration

---

### Risk control logic

apps/api/app/services/risk_engine.py


Handles:

- risk validation
- exposure checks
- runtime policies

---

### Trading guardrails

apps/api/app/services/trading_controls.py


Handles:

- kill switch
- trading enable/disable
- runtime safety checks

---

### Position flows

apps/api/app/api/positions.py


Handles:

- position state
- position creation from signals

---

# Broker Execution Layer

apps/worker/app/engine/


Contains runtime broker execution code.

Main modules:

execution_runtime.py
binance_client.py
ibkr_client.py


Responsibilities:

- broker order submission
- broker response normalization
- execution error handling

---

# Supporting Components

### Binance gateway

apps/binance_gateway/


Provides broker connectivity support.

---

# Scripts

scripts/

Contains operational scripts and maintenance utilities.

Examples:

- validation scripts
- operational checks
- recovery helpers

---

# Tests

tests/

Contains:

- unit tests
- operational validations
- regression checks

---

# Infrastructure

Root infrastructure files:


Dockerfile
docker-compose.yml
requirements.txt
render.yaml


These define:

- runtime environment
- service configuration
- deployment setup

---

# Where to Start Reading the Code

Recommended order:

1. AGENTS.md
2. docs/ARCHITECTURE.md
3. docs/TRADING_ENGINE.md
4. docs/RISK_MODEL.md
5. docs/REPOSITORY_MAP.md

Then inspect core modules:

1. apps/api/app/api/ops.py
2. apps/api/app/services/trading_controls.py
3. apps/api/app/services/risk_engine.py
4. apps/api/app/main.py
5. apps/worker/app/engine/execution_runtime.py

This sequence gives the fastest understanding of the system.
