from decimal import Decimal, InvalidOperation
from typing import Any


def _to_str(v: Any) -> str:
    return str(v)


def map_execution_report_to_binance_fill(message: dict) -> dict | None:
    if not isinstance(message, dict):
        return None

    event = message.get("event")
    if not isinstance(event, dict):
        return None

    if event.get("e") != "executionReport":
        return None

    if event.get("x") != "TRADE":
        return None

    trade_id = event.get("t")
    order_id = event.get("i")

    if trade_id is None or trade_id == -1:
        return None

    if order_id is None:
        return None

    qty = event.get("l")
    price = event.get("L")

    if qty is None or price is None:
        return None

    try:
        quote_qty = (Decimal(str(qty)) * Decimal(str(price)))
    except (InvalidOperation, TypeError):
        return None

    return {
        "id": _to_str(trade_id),
        "tradeId": _to_str(trade_id),
        "orderId": _to_str(order_id),
        "symbol": _to_str(event.get("s")),
        "side": _to_str(event.get("S")),
        "qty": _to_str(qty),
        "price": _to_str(price),
        "quoteQty": _to_str(quote_qty),
        "commission": _to_str(event.get("n") or "0"),
        "commissionAsset": (
            _to_str(event.get("N")) if event.get("N") is not None else None
        ),
        "time": event.get("T"),
        "rawWsEvent": event,
    }
