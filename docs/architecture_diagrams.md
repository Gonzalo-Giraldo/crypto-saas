# Architecture Diagrams

## Current Architecture Diagram
```mermaid
graph TD
    API --> ExecutionEngine
    ExecutionEngine --> BrokerRegistry
    BrokerRegistry --> BrokerAdapter
    BrokerAdapter --> BrokerClient
    BrokerClient --> Broker
```

## Order Lifecycle Diagram
```mermaid
graph TD
    User --> API
    API --> ExecutionEngine
    ExecutionEngine --> BrokerAdapter
    BrokerAdapter --> Broker
    Broker --> ExecutionEngine
    ExecutionEngine --> AuditLog
```

## Execution Engine Internal Diagram
```mermaid
graph TD
    ExecutionEngine --> RetrySeam
    ExecutionEngine --> ReconciliationSeam
    ExecutionEngine --> Audit
    ExecutionEngine --> Observability
```

## Broker Support Diagram
```mermaid
graph TD
    BrokerRegistry --> BinanceAdapter
    BrokerRegistry --> IBKRAdapter
```

## Future System Evolution Diagram
```mermaid
graph TD
    ExecutionEngine --> RiskEngine
    ExecutionEngine --> PortfolioEngine
    ExecutionEngine --> StrategyEngine
```

## Development-Flow Diagram
```mermaid
graph TD
    Design --> Implement
    Implement --> Test
    Test --> Commit
    Commit --> Document
    Document --> CommitDocs
```
