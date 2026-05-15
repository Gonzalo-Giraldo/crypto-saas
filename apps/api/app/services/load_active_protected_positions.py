from __future__ import annotations

from apps.api.app.models.binance_exit_protection import BinanceExitProtection


def load_active_protected_positions(db) -> list[dict]:
    rows = (
        db.query(BinanceExitProtection)
        .filter(BinanceExitProtection.market == "FUTURES")
        .filter(BinanceExitProtection.protection_status == "PROTECTED")
        .filter(BinanceExitProtection.sl_status == "SUBMITTED")
        .all()
    )

    return [
        {
            "exit_key": row.exit_key,
            "symbol": row.symbol,
            "market": row.market,
            "direction": row.direction,
            "filled_qty": row.filled_qty,
            "avg_entry_price": row.avg_entry_price,
            "sl_client_algo_id": row.sl_client_algo_id,
            "tp_client_algo_id": row.tp_client_algo_id,
            "sl_status": row.sl_status,
            "tp_status": row.tp_status,
            "protection_status": row.protection_status,
        }
        for row in rows
    ]
