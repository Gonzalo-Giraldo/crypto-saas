from __future__ import annotations

from apps.worker.app.engine.exit_manager import simulate_trailing_for_position


def run_trailing_stop_replacement_once(
    *,
    position: dict,
    old_sl_client_algo_id: str,
    replacement_client_order_id: str,
    replace_stop_loss,
) -> dict:
    old_sl_id = str(old_sl_client_algo_id or "").strip()
    if not old_sl_id:
        return {
            "status": "blocked",
            "reason": "old_sl_client_algo_id_required",
        }

    replacement_id = str(replacement_client_order_id or "").strip()
    if not replacement_id:
        return {
            "status": "blocked",
            "reason": "replacement_client_order_id_required",
        }

    decision = simulate_trailing_for_position(position)
    if decision is None:
        return {
            "status": "noop",
            "reason": "no_trailing_candidate",
        }

    direction = str(position.get("direction") or "").upper().strip()
    if direction not in {"LONG", "SHORT"}:
        return {
            "status": "blocked",
            "reason": "direction_required",
        }

    qty = position.get("qty")
    if qty is None:
        return {
            "status": "blocked",
            "reason": "qty_required",
        }

    return replace_stop_loss(
        symbol=decision["symbol"],
        direction=direction,
        qty=qty,
        entry_price=decision["entry_price"],
        old_stop_loss=decision["old_sl"],
        new_stop_loss=decision["new_sl"],
        old_sl_client_algo_id=old_sl_id,
        replacement_client_order_id=replacement_id,
    )
