from typing import Any, Dict


def db_like_persistence_callable(**kwargs) -> Dict[str, Any]:
    """
    Simula la firma y comportamiento esperado del backend de fills.
    SIN tocar DB real.
    """

    fills = kwargs.get("fills") or []
    user_id = kwargs.get("user_id")
    account_id = kwargs.get("account_id")
    broker = kwargs.get("broker")
    market = kwargs.get("market")

    if not user_id or not account_id:
        raise ValueError("user_id and account_id required")

    inserted_trade_ids = []
    skipped_trade_ids = []

    seen = set()

    for f in fills:
        trade_id = f.get("tradeId")
        order_id = f.get("orderId")

        if not trade_id:
            raise ValueError("tradeId required")
        if not order_id:
            raise ValueError("orderId required")

        key = (user_id, account_id, broker, market, trade_id)

        if key in seen:
            skipped_trade_ids.append(trade_id)
            continue

        seen.add(key)
        inserted_trade_ids.append(trade_id)

    return {
        "inserted": len(inserted_trade_ids),
        "skipped": len(skipped_trade_ids),
        "inserted_trade_ids": inserted_trade_ids,
        "skipped_trade_ids": skipped_trade_ids,
    }
