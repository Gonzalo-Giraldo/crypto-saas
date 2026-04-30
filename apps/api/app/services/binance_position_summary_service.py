from __future__ import annotations

from typing import Any

from sqlalchemy import text


def get_binance_position_summary_from_fills(*, db: Any, user_id: str) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                user_id,
                broker,
                account_id,
                market,
                symbol,
                COALESCE(SUM(CASE WHEN UPPER(side) = 'BUY' THEN qty ELSE 0 END), 0) AS buy_qty,
                COALESCE(SUM(CASE WHEN UPPER(side) = 'SELL' THEN qty ELSE 0 END), 0) AS sell_qty,
                COALESCE(SUM(CASE WHEN UPPER(side) = 'BUY' THEN quote_qty ELSE 0 END), 0) AS buy_usdt,
                COALESCE(SUM(CASE WHEN UPPER(side) = 'SELL' THEN quote_qty ELSE 0 END), 0) AS sell_usdt,
                COALESCE(SUM(commission_usdt), 0) AS commission_usdt
            FROM binance_fills
            WHERE user_id = :user_id
              AND broker = 'BINANCE'
            GROUP BY user_id, broker, account_id, market, symbol
            ORDER BY broker, account_id, market, symbol
            """
        ),
        {"user_id": str(user_id)},
    ).mappings().all()

    result = []
    for row in rows:
        buy_qty = row["buy_qty"]
        sell_qty = row["sell_qty"]
        buy_usdt = row["buy_usdt"]
        sell_usdt = row["sell_usdt"]
        commission_usdt = row["commission_usdt"]
        net_qty = buy_qty - sell_qty

        total_open_cost_simple = None
        avg_price_simple = None
        if sell_qty == 0 and net_qty:
            total_open_cost_simple = buy_usdt + commission_usdt
            avg_price_simple = total_open_cost_simple / net_qty

        result.append(
            {
                "user_id": str(row["user_id"]),
                "broker": row["broker"],
                "account_id": row["account_id"],
                "market": row["market"],
                "symbol": row["symbol"],
                "buy_qty": str(buy_qty),
                "sell_qty": str(sell_qty),
                "net_qty": str(net_qty),
                "buy_usdt": str(buy_usdt),
                "sell_usdt": str(sell_usdt),
                "commission_usdt": str(commission_usdt),
                "total_open_cost_simple": str(total_open_cost_simple) if total_open_cost_simple is not None else None,
                "avg_price_simple": str(avg_price_simple) if avg_price_simple is not None else None,
                "avg_price_method": "simple_only_valid_without_sells" if sell_qty == 0 else "not_computed_when_sells_exist",
            }
        )

    return result
