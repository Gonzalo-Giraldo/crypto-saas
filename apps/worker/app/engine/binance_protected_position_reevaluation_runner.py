from __future__ import annotations

from apps.worker.app.engine.exit_manager import simulate_trailing_for_position
from apps.worker.app.engine.binance_trailing_stop_runtime_gate import (
    can_run_trailing_stop_replacement,
)
from apps.worker.app.engine.binance_trailing_stop_orchestrator import (
    run_trailing_stop_replacement_once,
)

def reevaluate_protected_position_once(
    *,
    position: dict,
    protection_reconciliation: dict,
    old_sl_client_algo_id: str,
    replacement_client_order_id: str,
    transition_claim: dict | None,
    run_replacement,
) -> dict:
    trailing_decision = simulate_trailing_for_position(position)

    gate = can_run_trailing_stop_replacement(
        protection_reconciliation=protection_reconciliation,
        trailing_decision=trailing_decision,
        old_sl_client_algo_id=old_sl_client_algo_id,
        transition_claim=transition_claim,
    )
    if gate.get("allowed") is not True:
        return {
            "status": "blocked" if gate.get("reason") != "no_trailing_candidate" else "noop",
            "reason": gate.get("reason"),
        }

    return run_trailing_stop_replacement_once(
        position=position,
        old_sl_client_algo_id=old_sl_client_algo_id,
        replacement_client_order_id=replacement_client_order_id,
        replace_stop_loss=run_replacement,
    )
