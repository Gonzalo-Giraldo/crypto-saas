from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.app.services.runtime_orchestrator import run_binance_trading_cycle


def run_modular_shadow_trading_tick(
    *,
    db: Session,
    account_id: str = "default",
) -> dict:
    """
    Modular scheduler runner.

    SAFE MODE:
    - does not import ops.py
    - does not persist intents
    - does not execute broker orders
    - does not change Auto-Pick/Risk/Intent math
    """

    binance = run_binance_trading_cycle(
        db=db,
        account_id=account_id,
        persist_intent=False,
        execute_real=False,
        execution_authorized=False,
    )

    return {
        "status": "ok",
        "binance": binance,
        "persisted": False,
        "executed": False,
    }
