from typing import Dict


def compute_take_profit(
    entry_price: float,
    stop_loss: float,
    side: str,
    target_rr: float,
    min_rr: float,
) -> Dict:
    """
    Construye TP basado en RR.

    No usa mercado aún (estructura vendrá después).
    """

    if entry_price <= 0:
        raise ValueError("invalid entry_price")

    if stop_loss <= 0:
        raise ValueError("invalid stop_loss")

    if target_rr <= 0:
        raise ValueError("invalid target_rr")

    side = side.upper()

    # distancia de riesgo
    risk_abs = abs(entry_price - stop_loss)
    if risk_abs <= 0:
        raise ValueError("invalid risk_abs")

    # TP teórico
    if side == "BUY":
        tp = entry_price + (risk_abs * target_rr)
        reward = tp - entry_price
    elif side == "SELL":
        tp = entry_price - (risk_abs * target_rr)
        reward = entry_price - tp
    else:
        raise ValueError("invalid side")

    # RR real
    rr_real = reward / risk_abs if risk_abs > 0 else 0

    if rr_real < min_rr:
        raise ValueError(
            f"RR below minimum: rr={rr_real:.4f} min_rr={min_rr:.4f}"
        )

    return {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk_abs": risk_abs,
        "target_rr": target_rr,
        "tp": tp,
        "reward": reward,
        "rr_real": rr_real,
    }
