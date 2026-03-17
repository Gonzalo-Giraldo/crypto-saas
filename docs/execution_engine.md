# Execution Engine

## Components
- **execution_runtime**: Orchestrates order lifecycle, retry, reconciliation, audit, and observability.
- **broker_registry**: Resolves and manages broker adapters.
- **broker_adapter**: Abstracts broker-specific logic.
- **broker_client**: Handles direct broker API calls.

## Retry Seam
- Broker-agnostic, single-retry logic for transient errors (e.g., 502 gateway)

## Reconciliation Seam
- Broker-agnostic, client_order_id-driven reconciliation via adapter.query_order

## Audit
- All order lifecycle events are audit-logged

## Observability Counters
- In-process counters for sent, failed, retried, reconciled, and cancelled orders
