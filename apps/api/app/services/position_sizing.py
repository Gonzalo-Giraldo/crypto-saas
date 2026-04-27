from typing import Dict


def compute_position_size(
    entry_price: float,
    stop_loss: float,
    capital_base: float,
    risk_pct: float,
    max_exposure: float = 1.0,
) -> Dict:
    """
    Calcula qty basado en riesgo + SL + control de exposición.

    No depende de Binance, no normaliza, no ejecuta.
    Solo matemática pura.
    """

    if entry_price <= 0:
        raise ValueError("invalid entry_price")

    if stop_loss <= 0:
        raise ValueError("invalid stop_loss")

    if capital_base <= 0:
        raise ValueError("invalid capital_base")

    if risk_pct <= 0:
        raise ValueError("invalid risk_pct")

    # distancia al stop
    risk_abs = abs(entry_price - stop_loss)
    if risk_abs <= 0:
        raise ValueError("invalid risk_abs")

    # riesgo monetario permitido
    risk_usdt = capital_base * (risk_pct / 100.0)

    # qty teórica
    qty_raw = risk_usdt / risk_abs

    # control de exposición
    max_notional = capital_base * max_exposure
    qty_cap = max_notional / entry_price

    qty_final = min(qty_raw, qty_cap)

    # riesgo real resultante
    risk_real = qty_final * risk_abs

    return {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "capital_base": capital_base,
        "risk_pct": risk_pct,
        "risk_usdt": risk_usdt,
        "risk_abs": risk_abs,
        "qty_raw": qty_raw,
        "qty_cap": qty_cap,
        "qty_final": qty_final,
        "risk_real": risk_real,
    }
