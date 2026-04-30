from __future__ import annotations

from apps.api.app.services.intent_math import build_fixed_reward_risk_plan
from apps.api.app.services.position_sizing import compute_position_size
from apps.api.app.services.auto_pick.contracts import RiskSizingDecision


def build_risk_sizing_decision(
    *,
    side: str,
    entry_price: float,
    capital_base: float,
    risk_pct: float,
    reward_risk_ratio: float,
) -> RiskSizingDecision:
    """
    Orquestador de Risk.

    ⚠️ No introduce lógica nueva.
    ⚠️ Solo envuelve resultados de cálculos existentes.
    ⚠️ No toca DB, broker ni AutoPick.
    """

    plan = build_fixed_reward_risk_plan(
        side=side,
        entry_price=entry_price,
        risk_pct=risk_pct,
        reward_risk_ratio=reward_risk_ratio,
    )

    size = compute_position_size(
        entry_price=entry_price,
        stop_loss=plan.stop_loss,
        capital_base=capital_base,
        risk_pct=risk_pct,
    )

    return RiskSizingDecision(
        entry_price=entry_price,
        stop_loss=plan.stop_loss,
        take_profit=plan.take_profit,
        risk_pct=risk_pct,
        risk_abs=plan.risk_abs,
        expected_qty=size["qty_final"],
        evidence={
            "risk_usdt": size["risk_usdt"],
            "risk_real": size["risk_real"],
        },
    )
