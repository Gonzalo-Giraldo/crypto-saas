from typing import Any


def parse_execution_report_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Parse a Binance Spot WebSocket API userDataStream executionReport event.

    This parser is intentionally pure and isolated:
    - No DB writes
    - No network calls
    - No SQLAlchemy imports
    - No execution/risk/intent integration
    - No PnL calculation

    Accepted payload shape:
        {"subscriptionId": 0, "event": {...}}

    A valid fill candidate requires:
    - event.e == "executionReport"
    - event.x == "TRADE"
    - event.t exists and is not -1

    Important:
    - event.X is order status and can be FILLED or PARTIALLY_FILLED for real fills.
    - qty uses event.l, the last executed quantity for this fill.
    - event.z is cumulative executed quantity and must not be used as fill qty.
    """
    if not isinstance(payload, dict):
        return None

    event = payload.get("event")
    if not isinstance(event, dict):
        return None

    if event.get("e") != "executionReport":
        return None

    if event.get("x") != "TRADE":
        return None

    trade_id = event.get("t")
    if trade_id is None or str(trade_id) == "-1":
        return None

    order_id = event.get("i")
    if order_id is None:
        return None

    return {
        "broker": "BINANCE",
        "market": "SPOT",
        "symbol": event.get("s"),
        "side": event.get("S"),
        "order_id": str(order_id),
        "trade_id": str(trade_id),
        "qty": event.get("l"),
        "price": event.get("L"),
        "quote_qty": event.get("Z"),
        "commission": event.get("n"),
        "commission_asset": event.get("N"),
        "executed_at_ms": event.get("T"),
        "raw_event": event,
    }
