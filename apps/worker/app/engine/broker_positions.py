
from typing import List, Dict
from apps.worker.app.engine.binance_client import _post_gateway


def get_binance_positions(api_key: str, api_secret: str) -> List[Dict]:
    """
    Obtiene posiciones abiertas desde Binance Futures vía gateway.
    """

    data = _post_gateway(
        "/binance/position-risk", {
            "api_key": api_key,
            "api_secret": api_secret,
        },
    )

    
    if not isinstance(data, dict):
        raise RuntimeError(f"binance_position_risk_invalid_type {type(data)}")

    raw_positions = data.get("positions")
    if not isinstance(raw_positions, list):
        raise RuntimeError("binance_position_risk_missing_positions")

    positions = []


    for p in raw_positions:
        amt = float(p.get("positionAmt", "0") or 0)
        if amt == 0.0:
            continue

        side = "BUY" if amt > 0 else "SELL"

        positions.append({
            "broker": "BINANCE",
            "symbol": p.get("symbol"),
            "side": side,
            "qty": abs(amt),
            "entry_price": float(p.get("entryPrice", 0)),
            "current_price": float(p.get("markPrice", 0)),
            "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
        })

    return positions


def get_open_positions(user_id: str) -> List[Dict]:
    """
    Capa unificada para obtener posiciones abiertas desde brokers.
    """

    raise RuntimeError("broker_positions_requires_explicit_credentials")
