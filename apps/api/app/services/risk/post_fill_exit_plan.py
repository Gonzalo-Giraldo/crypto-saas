from __future__ import annotations

from apps.api.app.services.intent_math import IntentRiskPlan, build_fixed_reward_risk_plan


def build_post_fill_reward_risk_plan(
    *,
    side: str,
    avg_entry_price: float,
    risk_pct: float,
    reward_risk_ratio: float,
) -> IntentRiskPlan:
    """
    PURE FUNCTION.

    Reuses the existing risk/reward formula.
    NO new financial math.
    NO DB.
    NO broker.
    NO runtime.
    """

    return build_fixed_reward_risk_plan(
        side=side,
        entry_price=avg_entry_price,
        risk_pct=risk_pct,
        reward_risk_ratio=reward_risk_ratio,
    )
