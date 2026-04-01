IBKR BRIDGE ARCHITECTURE

Flow:
client → bridge (FastAPI) → core_router → module → runtime (files)

Components:

1. ibkr_runtime_bridge.py
- HTTP layer only
- no business logic

2. ibkr_core_router.py
- routes actions to modules
- no execution logic

3. m_ibkr_bridge/
- isolated modules per function
  - order_module
  - status_module
  - health_module

Rules:
- modules do not call each other
- core does not execute logic
- bridge does not contain logic
- runtime is external and untouched

Goal:
avoid coupling, enable safe evolution, prevent regressions
