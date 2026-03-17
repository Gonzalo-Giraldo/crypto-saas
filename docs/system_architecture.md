# System Architecture

## Overall Platform Architecture
The platform is composed of modular engines for execution, risk, portfolio, and strategy. Each engine is designed for clear separation of concerns and broker-agnostic extensibility.

## Current Execution Engine Architecture
- **execution_runtime**: Orchestrates order lifecycle, retry, reconciliation, audit, and observability.
- **broker_registry**: Resolves broker adapters.
- **broker_adapter**: Abstracts broker-specific logic.
- **broker_client**: Handles direct broker API calls.

## Principles of Design
- Broker-agnostic core
- Explicit audit and observability
- Minimal, testable seams for retry and reconciliation
- Incremental hardening and extensibility

## Roadmap Phases 11–15
- 11: Implement risk engine and pre-trade controls
- 12: Portfolio engine for positions and PnL
- 13: Strategy engine for signal and intent
- 14: Production hardening and monitoring
- 15: Documentation and developer experience
