from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any, field: str) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        out = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field}_invalid") from None
    if not out.is_finite():
        raise ValueError(f"{field}_not_finite")
    return out


def _required_str(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{field}_required")
    return out


def derive_binance_positions_from_fill_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("rows_must_be_list")

    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("fill_row_must_be_dict")

        user_id = _required_str(row.get("user_id"), "user_id")
        account_id = _required_str(row.get("account_id"), "account_id")
        broker = _required_str(row.get("broker"), "broker").upper()
        market = _required_str(row.get("market"), "market").upper()
        symbol = _required_str(row.get("symbol"), "symbol").upper()
        side = _required_str(row.get("side"), "side").upper()

        if broker != "BINANCE":
            raise ValueError("broker_must_be_BINANCE")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side_invalid")

        qty = _decimal(row.get("qty"), "qty")
        quote_qty = _decimal(row.get("quote_qty"), "quote_qty")
        commission_usdt = _decimal(row.get("commission_usdt"), "commission_usdt")

        if qty < 0:
            raise ValueError("qty_negative")
        if quote_qty < 0:
            raise ValueError("quote_qty_negative")
        if commission_usdt < 0:
            raise ValueError("commission_usdt_negative")

        key = (user_id, account_id, broker, market, symbol)

        if key not in grouped:
            grouped[key] = {
                "user_id": user_id,
                "account_id": account_id,
                "broker": broker,
                "market": market,
                "symbol": symbol,
                "buy_qty": Decimal("0"),
                "sell_qty": Decimal("0"),
                "net_qty": Decimal("0"),
                "buy_quote_usdt": Decimal("0"),
                "sell_quote_usdt": Decimal("0"),
                "commission_usdt": Decimal("0"),
                "fills_count": 0,
                "position_status": "CLOSED",
            }

        out = grouped[key]

        if side == "BUY":
            out["buy_qty"] += qty
            out["buy_quote_usdt"] += quote_qty
        else:
            out["sell_qty"] += qty
            out["sell_quote_usdt"] += quote_qty

        out["commission_usdt"] += commission_usdt
        out["fills_count"] += 1
        out["net_qty"] = out["buy_qty"] - out["sell_qty"]
        out["position_status"] = "OPEN" if out["net_qty"] != Decimal("0") else "CLOSED"

    return sorted(
        grouped.values(),
        key=lambda row: (
            row["user_id"],
            row["account_id"],
            row["broker"],
            row["market"],
            row["symbol"],
        ),
    )
