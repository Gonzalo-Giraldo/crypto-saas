from typing import Any, Callable

from apps.binance_ws_worker.fill_mapper import map_execution_report_to_binance_fill


def persist_ws_execution_report_message(
    *,
    db: Any,
    message: dict,
    user_id: str,
    account_id: str,
    persist_callable: Callable[..., Any],
    broker: str = "BINANCE",
    market: str = "SPOT",
) -> dict:
    fill = map_execution_report_to_binance_fill(message)

    if fill is None:
        return {
            "processed": False,
            "reason": "not_a_fill",
            "inserted": 0,
            "skipped": 0,
            "trade_id": None,
            "order_id": None,
        }

    result = persist_callable(
        db=db,
        fills=[fill],
        user_id=user_id,
        account_id=account_id,
        broker=broker,
        market=market,
    )

    inserted = int((result or {}).get("inserted", 0))
    skipped = int((result or {}).get("skipped", 0))

    return {
        "processed": True,
        "reason": "fill",
        "inserted": inserted,
        "skipped": skipped,
        "trade_id": fill.get("tradeId"),
        "order_id": fill.get("orderId"),
    }
