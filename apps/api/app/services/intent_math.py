from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentRiskPlan:
    side: str
    entry_price: float
    risk_pct: float
    reward_risk_ratio: float
    risk_abs: float
    stop_loss: float
    take_profit: float


def build_fixed_reward_risk_plan(
    *,
    side: str,
    entry_price: float,
    risk_pct: float,
    reward_risk_ratio: float,
) -> IntentRiskPlan:
    side_norm = str(side or "").upper().strip()
    entry = float(entry_price)
    risk_pct_value = float(risk_pct)
    rr = float(reward_risk_ratio)

    if side_norm not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if entry <= 0:
        raise ValueError("entry_price must be positive")
    if risk_pct_value <= 0:
        raise ValueError("risk_pct must be positive")
    if rr <= 0:
        raise ValueError("reward_risk_ratio must be positive")

    risk_abs = entry * (risk_pct_value / 100.0)
    if risk_abs <= 0:
        raise ValueError("risk_abs must be positive")

    if side_norm == "BUY":
        stop_loss = entry - risk_abs
        take_profit = entry + (risk_abs * rr)
    else:
        stop_loss = entry + risk_abs
        take_profit = entry - (risk_abs * rr)

    if stop_loss <= 0 or take_profit <= 0:
        raise ValueError("calculated prices must be positive")

    return IntentRiskPlan(
        side=side_norm,
        entry_price=entry,
        risk_pct=risk_pct_value,
        reward_risk_ratio=rr,
        risk_abs=risk_abs,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
