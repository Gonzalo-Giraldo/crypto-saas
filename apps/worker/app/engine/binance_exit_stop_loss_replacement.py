from __future__ import annotations

from decimal import Decimal

from apps.worker.app.engine.binance_futures_exit_orders import (
    build_binance_futures_stop_loss_order,
)


_ACTIVE_ALGO_STATUSES = {
    "NEW",
    "WORKING",
    "ACCEPTED",
}


def _is_favorable_replacement(
    *,
    direction: str,
    old_stop_loss: str,
    new_stop_loss: str,
) -> bool:
    old_sl = Decimal(str(old_stop_loss))
    new_sl = Decimal(str(new_stop_loss))

    direction_norm = str(direction or "").upper().strip()

    if direction_norm == "LONG":
        return new_sl > old_sl

    if direction_norm == "SHORT":
        return new_sl < old_sl

    raise ValueError("unsupported_direction")


def replace_exit_stop_loss_authoritatively(
    *,
    symbol: str,
    direction: str,
    qty: str,
    entry_price: str,
    old_stop_loss: str,
    new_stop_loss: str,
    old_sl_client_algo_id: str,
    replacement_client_order_id: str,
    create_sl_order,
    fetch_sl_status,
    cancel_old_sl,
):
    if not _is_favorable_replacement(
        direction=direction,
        old_stop_loss=old_stop_loss,
        new_stop_loss=new_stop_loss,
    ):
        return {
            "status": "blocked",
            "reason": "non_favorable_replacement_sl",
        }

    stop_loss_order = build_binance_futures_stop_loss_order(
        symbol=symbol,
        direction=direction,
        qty=qty,
        stop_loss=new_stop_loss,
        client_order_id=replacement_client_order_id,
    )

    create_result = create_sl_order(stop_loss_order)

    if create_result.get("status") != "OK":
        return {
            "status": "blocked",
            "reason": "replacement_sl_create_failed",
        }

    status_result = fetch_sl_status(
        client_algo_id=stop_loss_order["clientAlgoId"],
    )

    response = status_result.get("response") or {}
    algo_status = str(response.get("status") or "").upper().strip()

    if algo_status not in _ACTIVE_ALGO_STATUSES:
        return {
            "status": "blocked",
            "reason": "replacement_sl_not_active",
        }

    cancel_result = cancel_old_sl(
        client_algo_id=old_sl_client_algo_id,
    )

    if isinstance(cancel_result, dict):
        cancel_status = str(cancel_result.get("status") or "").upper().strip()
        cancel_ok = cancel_status in {"CANCELED", "CANCELLED"}
    else:
        cancel_ok = False

    if not cancel_ok:
        return {
            "status": "replacement_pending_cleanup",
            "reason": "old_sl_cancel_failed",
            "old_sl_client_algo_id": old_sl_client_algo_id,
            "new_sl_client_algo_id": stop_loss_order["clientAlgoId"],
            "new_sl_algo_id": response.get("algoId"),
        }

    return {
        "status": "replaced",
        "old_sl_client_algo_id": old_sl_client_algo_id,
        "new_sl_client_algo_id": stop_loss_order["clientAlgoId"],
        "new_sl_algo_id": response.get("algoId"),
    }
