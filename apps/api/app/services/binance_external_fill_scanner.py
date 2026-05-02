from sqlalchemy import text
from typing import Dict, Any, List

def scan_binance_external_fills(
    db,
    user_id: str,
    account_id: str,
    symbol: str,
    market: str,
    api_key: str,
    api_secret: str,
    fetch_binance_trades,
    persist_binance_fills_db,
) -> Dict[str, Any]:
    if market != "SPOT":
        raise ValueError("market_not_supported")

    symbol = symbol.upper()

    trades = fetch_binance_trades(
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        market=market,
    ) or []

    scanned_count = len(trades)

    rows = db.execute(
        text("""
        SELECT trade_id
        FROM binance_fills
        WHERE user_id = :user_id
          AND account_id = :account_id
          AND symbol = :symbol
          AND market = :market
          AND broker = 'BINANCE'
        """),
        {
            "user_id": str(user_id),
            "account_id": account_id,
            "symbol": symbol,
            "market": market,
        }
    ).fetchall()

    existing_ids = {str(r[0]) for r in rows if r[0] is not None}

    new_trades = []
    skipped_existing_count = 0

    for t in trades:
        raw_id = t.get("id") or t.get("trade_id")

        # 🔴 VALIDACIÓN CRÍTICA
        if raw_id is None:
            continue

        trade_id = str(raw_id)

        if trade_id in existing_ids:
            skipped_existing_count += 1
            continue

        new_trades.append(t)

    inserted_trade_ids: List[str] = []

    if new_trades:
        result = persist_binance_fills_db(
            db=db,
            trades=new_trades,
            user_id=user_id,
            account_id=account_id,
            market=market,
        ) or []

        for r in result:
            rid = r.get("trade_id") or r.get("id")
            if rid is not None:
                inserted_trade_ids.append(str(rid))

    return {
        "scanned_count": scanned_count,
        "inserted_count": len(inserted_trade_ids),
        "skipped_existing_count": skipped_existing_count,
        "inserted_trade_ids": inserted_trade_ids,
    }
