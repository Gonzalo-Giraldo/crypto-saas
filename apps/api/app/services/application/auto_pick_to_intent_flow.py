from __future__ import annotations

from apps.api.app.services.auto_pick.contracts import (
    AutoPickDecision,
    IntentCreateDraft,
)
from apps.api.app.services.risk.risk_orchestrator import build_risk_sizing_decision


def build_intent_draft_from_autopick(
    *,
    decision: AutoPickDecision,
    capital_base: float,
    risk_pct: float,
    reward_risk_ratio: float,
) -> IntentCreateDraft:
    """
    Application flow: AutoPickDecision -> RiskSizingDecision -> IntentCreateDraft.

    No DB.
    No broker.
    No execution.
    No financial formulas.
    """

    if not isinstance(decision, AutoPickDecision):
        raise ValueError("decision must be AutoPickDecision")

    entry_price_reference = decision.evidence.get("entry_price_reference")
    if entry_price_reference is None:
        raise ValueError("entry_price_reference is required")

    risk_sizing = build_risk_sizing_decision(
        side=decision.side,
        entry_price=float(entry_price_reference),
        capital_base=capital_base,
        risk_pct=risk_pct,
        reward_risk_ratio=reward_risk_ratio,
    )

    return IntentCreateDraft(
        broker=decision.broker,
        symbol=decision.symbol,
        side=decision.side,
        direction=decision.direction,
        asset_profile=decision.asset_profile,
        model_version=decision.model_version,
        final_score=decision.final_score,
        decision_reason=decision.decision_reason,
        risk_sizing=risk_sizing,
        evidence=decision.evidence,
    )
