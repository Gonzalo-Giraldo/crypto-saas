from typing import Any, Callable, Dict, List, Optional, Set
from sqlalchemy import text


def _adapt_ws_fill_to_persistence(fill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    trade_id = fill.get("trade_id")
    order_id = fill.get("order_id")

    if not trade_id or str(trade_id) == "-1":
        return None

    if not order_id:
        return None

    return {
        "id": str(trade_id),
        "tradeId": str(trade_id),
        "orderId": str(order_id),
        "symbol": fill.get("symbol"),
        "side": fill.get("side"),
        "qty": fill.get("qty"),
        "price": fill.get("price"),
        "quoteQty": fill.get("quote_qty"),
        "commission": fill.get("commission"),
        "commissionAsset": fill.get("commission_asset"),
        "time": fill.get("executed_at_ms"),
    }


def _fetch_existing_trade_ids(
    db: Any,
    trade_ids: Set[str],
    user_id: str,
    account_id: str,
    broker: str,
    market: str,
) -> Set[str]:

    if not trade_ids:
        return set()

    executor = getattr(db, "execute", None)
    if executor is None and hasattr(db, "session"):
        executor = getattr(db.session, "execute", None)

    if executor is None:
        raise RuntimeError("DB object does not provide execute or session.execute")

    placeholders = ", ".join([f":t{i}" for i in range(len(trade_ids))])
    params = {f"t{i}": tid for i, tid in enumerate(trade_ids)}

    params.update({
        "user_id": user_id,
        "account_id": account_id,
        "broker": broker,
        "market": market,
    })

    query = f"""
    SELECT trade_id
    FROM binance_fills
    WHERE user_id = :user_id
      AND account_id = :account_id
      AND broker = :broker
      AND market = :market
      AND trade_id IN ({placeholders})
    """

    result = executor(text(query), params)
    rows = list(result)

    existing = set()
    for row in rows:
        if isinstance(row, (list, tuple)):
            existing.add(str(row[0]))
        elif hasattr(row, "trade_id"):
            existing.add(str(row.trade_id))
        else:
            existing.add(str(row))

    return existing


def persist_ws_binance_fill_candidates(
    *,
    db: Any,
    fill_candidates: List[Dict[str, Any]],
    user_id: str,
    account_id: str,
    persist_binance_fills_db_callable: Callable[..., Any],
) -> Dict[str, Any]:

    received = len(fill_candidates or [])

    if not fill_candidates:
        return {
            "received": 0,
            "inserted_candidate_count": 0,
            "skipped_existing_count": 0,
            "skipped_duplicate_in_batch_count": 0,
            "skipped_invalid_count": 0,
            "inserted_trade_ids": [],
            "skipped_trade_ids": [],
        }

    broker = "BINANCE"
    market = "SPOT"

    valid_candidates = []
    seen_batch: Set[str] = set()
    skipped_invalid = 0
    skipped_duplicate_batch = 0

    for fill in fill_candidates:
        trade_id = fill.get("trade_id")
        if not trade_id or str(trade_id) == "-1":
            skipped_invalid += 1
            continue

        tid = str(trade_id)

        if tid in seen_batch:
            skipped_duplicate_batch += 1
            continue

        seen_batch.add(tid)
        valid_candidates.append(fill)

    trade_ids = {str(f["trade_id"]) for f in valid_candidates}

    existing_ids = _fetch_existing_trade_ids(
        db,
        trade_ids,
        user_id,
        account_id,
        broker,
        market,
    )

    to_insert = []
    skipped_existing = 0
    skipped_trade_ids = []

    for fill in valid_candidates:
        tid = str(fill["trade_id"])
        if tid in existing_ids:
            skipped_existing += 1
            skipped_trade_ids.append(tid)
            continue

        adapted = _adapt_ws_fill_to_persistence(fill)
        if adapted is None:
            skipped_invalid += 1
            continue

        to_insert.append(adapted)

    inserted_trade_ids = [f["tradeId"] for f in to_insert]

    if to_insert:
        persist_binance_fills_db_callable(
            db=db,
            fills=to_insert,
            user_id=user_id,
            account_id=account_id,
            broker=broker,
            market=market,
        )

    return {
        "received": received,
        "inserted_candidate_count": len(to_insert),
        "skipped_existing_count": skipped_existing,
        "skipped_duplicate_in_batch_count": skipped_duplicate_batch,
        "skipped_invalid_count": skipped_invalid,
        "inserted_trade_ids": inserted_trade_ids,
        "skipped_trade_ids": skipped_trade_ids,
    }
