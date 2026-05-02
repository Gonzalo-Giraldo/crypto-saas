import os
from sqlalchemy import text
from typing import Dict, Any, List
import time

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
    start_time_ms: int = None,   # 🔴 NUEVO
) -> Dict[str, Any]:

    app_env = (os.getenv("APP_ENV") or "").strip().lower()
    environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
    allow_unsafe_manual_run = (
        os.getenv("BINANCE_EXTERNAL_FILL_SCANNER_ALLOW_UNSAFE_MANUAL_RUN")
        or ""
    ).strip().lower()

    if (
        app_env in {"production", "prod"}
        or environment in {"production", "prod"}
    ) and allow_unsafe_manual_run != "true":
        raise RuntimeError(
            "binance external fill scanner is blocked in production unless "
            "BINANCE_EXTERNAL_FILL_SCANNER_ALLOW_UNSAFE_MANUAL_RUN=true"
        )

    if market != "SPOT":
        raise ValueError("market_not_supported")

    symbol = symbol.upper()

    # 🔴 SI NO SE PASA → usar "ahora - 5 min"
    if start_time_ms is None:
        start_time_ms = int(time.time() * 1000) - (5 * 60 * 1000)

    trades = fetch_binance_trades(
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        market=market,
        start_time_ms=start_time_ms,   # 🔴 CLAVE
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
        raw_id = t.get("id") or t.get("tradeId")

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
            fills=new_trades,
            user_id=user_id,
            account_id=account_id,
            broker="BINANCE",
            market=market,
        ) or {}

        inserted_count = result.get("inserted", 0)

        inserted_trade_ids = [
            str(t.get("id") or t.get("tradeId"))
            for t in new_trades[:inserted_count]
        ]
    else:
        inserted_count = 0

    return {
        "scanned_count": scanned_count,
        "inserted_count": inserted_count,
        "skipped_existing_count": skipped_existing_count,
        "inserted_trade_ids": inserted_trade_ids,
    }
