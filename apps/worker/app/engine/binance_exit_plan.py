from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal_positive(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _side_to_direction(side: Any) -> str | None:
    normalized = str(side or "").upper().strip()
    if normalized == "BUY":
        return "LONG"
    if normalized == "SELL":
        return "SHORT"
    return None


def build_binance_exit_plan(
    *,
    symbol: Any,
    side: Any,
    fill_basis: dict[str, Any] | None,
    risk_inputs: dict[str, Any] | None,
    client_order_id: Any,
) -> dict[str, Any]:
    direction = _side_to_direction(side)
    if direction is None:
        return {"available": False, "reason": "invalid_side"}

    if not isinstance(fill_basis, dict) or fill_basis.get("usable_for_exits") is not True:
        return {"available": False, "reason": "fill_basis_not_usable"}

    if not isinstance(risk_inputs, dict) or risk_inputs.get("available") is not True:
        return {"available": False, "reason": "risk_inputs_not_available"}

    filled_qty = _decimal_positive(fill_basis.get("filled_qty"))
    avg_entry_price = _decimal_positive(fill_basis.get("avg_entry_price"))
    stop_loss = _decimal_positive(risk_inputs.get("stop_loss"))
    take_profit = _decimal_positive(risk_inputs.get("take_profit"))

    if filled_qty is None:
        return {"available": False, "reason": "filled_qty_invalid"}

    if avg_entry_price is None:
        return {"available": False, "reason": "avg_entry_price_invalid"}

    if stop_loss is None:
        return {"available": False, "reason": "stop_loss_invalid"}

    if take_profit is None:
        return {"available": False, "reason": "take_profit_invalid"}

    symbol_norm = str(symbol or "").upper().strip()
    if not symbol_norm:
        return {"available": False, "reason": "symbol_required"}

    client_id = str(client_order_id or "").strip()
    if not client_id:
        return {"available": False, "reason": "client_order_id_required"}

    return {
        "available": True,
        "reason": "ok",
        "symbol": symbol_norm,
        "direction": direction,
        "filled_qty": format(filled_qty, "f"),
        "avg_entry_price": format(avg_entry_price, "f"),
        "stop_loss": format(stop_loss, "f"),
        "take_profit": format(take_profit, "f"),
        "client_order_id": client_id,
    }
