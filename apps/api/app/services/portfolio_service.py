from __future__ import annotations

from sqlalchemy import text


def get_binance_portfolio_summary(db, user_id: str, account_id: str | None = None, broker_balances: dict[str, str] | None = None) -> list[dict]:
    params = {"user_id": str(user_id)}
    account_filter = ""

    if account_id is not None and str(account_id).strip():
        account_filter = "AND account_id = :account_id"
        params["account_id"] = str(account_id)

    rows = db.execute(
        text(
            f"""
            SELECT
              user_id,
              account_id,
              broker,
              market,
              symbol,

              SUM(CASE WHEN side = 'BUY' THEN qty ELSE -qty END) AS net_position_qty,

              SUM(CASE WHEN side = 'BUY' THEN quote_qty ELSE 0 END) AS buy_quote_usdt,
              SUM(CASE WHEN side = 'SELL' THEN quote_qty ELSE 0 END) AS sell_quote_usdt,

              SUM(COALESCE(commission_usdt, 0)) AS commission_usdt,
              SUM(COALESCE(realized_pnl, 0)) AS realized_pnl,

              CASE
                WHEN market = 'FUTURES'
                THEN SUM(COALESCE(realized_pnl, 0)) - SUM(COALESCE(commission_usdt, 0))
                ELSE NULL
              END AS net_pnl_futures_usdt,

              CASE
                WHEN market = 'SPOT'
                THEN SUM(CASE WHEN side = 'BUY' THEN quote_qty ELSE 0 END)
                ELSE NULL
              END AS spot_cost_usdt,

              CASE
                WHEN market = 'SPOT'
                THEN SUM(CASE WHEN side = 'BUY' THEN quote_qty ELSE 0 END) + SUM(COALESCE(commission_usdt, 0))
                ELSE NULL
              END AS spot_cost_with_fees_usdt

            FROM binance_fills
            WHERE user_id = :user_id
              {account_filter}
            GROUP BY user_id, account_id, broker, market, symbol
            ORDER BY market, symbol
            """
        ),
        params,
    ).mappings().all()

    result = [dict(row) for row in rows]

    balances = broker_balances or {}
    for row in result:
        if row.get("broker") != "BINANCE":
            continue
        if row.get("market") != "SPOT":
            continue

        symbol = str(row.get("symbol") or "").upper().strip()
        base_asset = symbol[:-4] if symbol.endswith("USDT") else symbol
        broker_qty_raw = balances.get(base_asset)

        if broker_qty_raw is None:
            row["broker_spot_balance_qty"] = None
            row["reconciliation_delta_qty"] = None
            row["reconciliation_status"] = "broker_balance_not_provided"
            continue

        try:
            broker_qty = float(broker_qty_raw)
            position_qty = float(row.get("net_position_qty") or 0)
        except Exception:
            row["broker_spot_balance_qty"] = str(broker_qty_raw)
            row["reconciliation_delta_qty"] = None
            row["reconciliation_status"] = "invalid_broker_balance"
            continue

        delta = broker_qty - position_qty
        row["broker_spot_balance_qty"] = broker_qty
        row["reconciliation_delta_qty"] = delta
        row["reconciliation_status"] = "matched" if abs(delta) < 1e-12 else "mismatch"

    return result
