from __future__ import annotations


def calculate_position_realized_pnl(
    *,
    side: str,
    entry_price: float,
    exit_price: float,
    qty: float,
    fees: float = 0.0,
) -> float:
    side_norm = str(side or "").upper().strip()
    entry = float(entry_price)
    exit_ = float(exit_price)
    quantity = float(qty)
    fee_value = float(fees or 0.0)

    if side_norm in {"BUY", "LONG"}:
        return (exit_ - entry) * quantity - fee_value

    if side_norm in {"SELL", "SHORT"}:
        return (entry - exit_) * quantity - fee_value

    raise ValueError("unsupported_position_side")
