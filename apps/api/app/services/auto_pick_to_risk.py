from __future__ import annotations

from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.risk.contracts import RiskSizingDecision
from apps.api.app.services.risk.risk_orchestrator import build_risk_sizing_decision


def build_risk_from_auto_pick_decision(
    *,
    decision: AutoPickDecision,
    capital_base: float,
    risk_pct: float,
    reward_risk_ratio: float,
) -> RiskSizingDecision:
    """
    Coordinate AutoPick -> Risk only.

    This function:
    - does not create intents
    - does not touch DB
    - does not call brokers
    - does not execute orders
    - does not treat entry_price_reference as a fill
    """

    if not isinstance(decision, AutoPickDecision):
        raise ValueError("auto_pick_decision_required")

    entry_price = decision.evidence.get("entry_price_reference")
    if entry_price is None:
        raise ValueError("entry_price_reference_required")

    try:
        entry_price_f = float(entry_price)
        capital_base_f = float(capital_base)
        risk_pct_f = float(risk_pct)
        reward_risk_ratio_f = float(reward_risk_ratio)
    except (TypeError, ValueError):
        raise ValueError("risk_input_invalid") from None

    if entry_price_f <= 0:
        raise ValueError("entry_price_reference_must_be_positive")
    if capital_base_f <= 0:
        raise ValueError("capital_base_must_be_positive")
    if risk_pct_f <= 0:
        raise ValueError("risk_pct_must_be_positive")
    if reward_risk_ratio_f <= 0:
        raise ValueError("reward_risk_ratio_must_be_positive")

    return build_risk_sizing_decision(
        side=decision.side,
        entry_price=entry_price_f,
        capital_base=capital_base_f,
        risk_pct=risk_pct_f,
        reward_risk_ratio=reward_risk_ratio_f,
    )
