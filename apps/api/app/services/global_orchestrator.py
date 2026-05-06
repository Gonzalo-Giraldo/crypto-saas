from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.app.services.scheduler_runtime import run_modular_shadow_trading_tick


def run_global_shadow_cycle(
    *,
    db: Session,
    account_id: str = "default",
) -> dict:
    """
    Global orchestrator.

    SAFE MODE:
    - does not import ops.py
    - does not contain financial math
    - does not call brokers directly
    - coordinates modular runtimes only
    """

    trading = run_modular_shadow_trading_tick(
        db=db,
        account_id=account_id,
    )

    return {
        "status": "ok",
        "trading": trading,
        "persisted": False,
        "executed": False,
    }
