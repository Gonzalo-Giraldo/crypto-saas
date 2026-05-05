from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


_USABLE_RECONCILIATION_STATUSES = {"matched", "partial", "overfilled"}


def _read_value(item: Any, key: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


def _to_positive_decimal(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None

    if parsed <= 0:
        return None

    return parsed


def _decimal_to_string(value: Decimal) -> str:
    return format(value, "f")


def derive_binance_entry_fill_basis(
    *,
    trades: list[Any] | tuple[Any, ...],
    reconciliation_status: str,
) -> dict[str, str | bool]:
    total_qty = Decimal("0")
    total_notional = Decimal("0")

    for trade in trades or []:
        qty = _to_positive_decimal(_read_value(trade, "qty"))
        price = _to_positive_decimal(_read_value(trade, "price"))

        if qty is None or price is None:
            continue

        total_qty += qty
        total_notional += qty * price

    if total_qty <= 0:
        return {
            "filled_qty": "0",
            "avg_entry_price": "0",
            "reconciliation_status": reconciliation_status,
            "usable_for_exits": False,
            "reason": "no_valid_fills",
        }

    avg_entry_price = total_notional / total_qty

    if reconciliation_status not in _USABLE_RECONCILIATION_STATUSES:
        return {
            "filled_qty": _decimal_to_string(total_qty),
            "avg_entry_price": _decimal_to_string(avg_entry_price),
            "reconciliation_status": reconciliation_status,
            "usable_for_exits": False,
            "reason": "reconciliation_status_not_usable",
        }

    return {
        "filled_qty": _decimal_to_string(total_qty),
        "avg_entry_price": _decimal_to_string(avg_entry_price),
        "reconciliation_status": reconciliation_status,
        "usable_for_exits": True,
        "reason": "ok",
    }
