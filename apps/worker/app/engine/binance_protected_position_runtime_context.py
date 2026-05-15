from __future__ import annotations


def build_protected_position_runtime_context(
    *,
    protected_position: dict,
    fetch_current_price,
) -> dict:
    market = str(protected_position.get("market") or "").upper().strip()
    if market != "FUTURES":
        return {
            "status": "blocked",
            "reason": "market_must_be_FUTURES",
        }

    symbol = str(protected_position.get("symbol") or "").upper().strip()
    direction = str(protected_position.get("direction") or "").upper().strip()

    current_price = fetch_current_price(symbol, market)
    if current_price is None:
        return {
            "status": "blocked",
            "reason": "current_price_unavailable",
        }

    side = "BUY" if direction == "LONG" else "SELL"

    return {
        "exit_key": protected_position.get("exit_key"),
        "old_sl_client_algo_id": protected_position.get("sl_client_algo_id"),
        "position": {
            "symbol": symbol,
            "side": side,
            "direction": direction,
            "entry_price": protected_position.get("avg_entry_price"),
            "stop_loss": protected_position.get("stop_loss"),
            "current_price": current_price,
            "qty": protected_position.get("filled_qty"),
            "intent_entry_price": protected_position.get("avg_entry_price"),
        },
    }
