# TRADING_ENGINE.md

## 1. Purpose

This document describes the **core trading decision and execution system** of the platform.

Its goal is to help engineers and AI agents understand:

- how trading decisions are made
- how signals become orders
- how balances and positions are used
- how quantity sizing works
- how execution is routed to brokers
- where operational risk exists

This document explains **business logic**, not infrastructure.

---

## 2. Trading Engine Overview

The trading engine converts **signals into broker orders** through a controlled pipeline.

Core responsibilities:

- validate signals
- apply risk controls
- check balances and exposure
- calculate order quantity
- select broker execution path
- prevent duplicate orders
- enforce paper/live separation
- produce auditable trading actions

The trading engine is safety-critical.

---

## 3. Main Trading Flow

The simplified execution pipeline is:

Signal received
↓
Pretrade validation
↓
Exposure and risk checks
↓
Auto-pick decision logic
↓
Quantity sizing
↓
Real-execution guards
↓
Broker execution runtime
↓
Audit logging and state updates

Each stage acts as a **safety gate**.

---

## 4. Signal Sources

Signals can originate from multiple sources.

### Manual signals

### Manual signal endpoints

POST /signals
GET /signals
POST /signals/claim

### Broker pretrade / auto-pick endpoints

POST /ops/execution/pretrade/binance/check
POST /ops/execution/pretrade/binance/scan
POST /ops/execution/pretrade/binance/auto-pick

POST /ops/execution/pretrade/ibkr/check
POST /ops/execution/pretrade/ibkr/scan
POST /ops/execution/pretrade/ibkr/auto-pick

### Position creation from signals

POST /positions/open_from_signal
