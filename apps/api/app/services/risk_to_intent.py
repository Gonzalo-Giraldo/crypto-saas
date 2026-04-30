from __future__ import annotations

from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.risk.contracts import RiskSizingDecision
from apps.api.app.services.binance_intent_adapter import create_binance_intent


def build_binance_intent_from_risk(
    *,
    decision: AutoPickDecision,
    risk: RiskSizingDecision,
):
    """
    Risk → Intent adapter.

    Reglas:
    - NO recalcula nada
    - NO toca DB directamente (lo hace create_intent)
    - NO introduce lógica financiera
    """

    if not isinstance(decision, AutoPickDecision):
        raise ValueError("auto_pick_decision_required")

    if not isinstance(risk, RiskSizingDecision):
        raise ValueError("risk_sizing_required")

    auto_pick_trace = {
        "final_score": decision.final_score,
        "decision_reason": decision.decision_reason,
        "evidence": decision.evidence,
    }

    return create_binance_intent(
        symbol=decision.symbol,
        side=decision.side,
        expected_qty=risk.expected_qty,
        entry_price=risk.entry_price,
        stop_loss=risk.stop_loss,
        take_profit=risk.take_profit,
        auto_pick_trace=auto_pick_trace,
    )
