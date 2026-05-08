from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.risk.contracts import RiskSizingDecision


@dataclass(frozen=True)
class BinanceIntentDraft:
    symbol: str
    side: str
    expected_qty: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_pct: float
    risk_abs: float
    risk_usdt: float | None
    reward_risk_ratio: float | None
    entry_price_reference: float
    auto_pick_trace: dict[str, Any]


def build_binance_intent_draft(
    *,
    decision: AutoPickDecision,
    risk: RiskSizingDecision,
) -> BinanceIntentDraft:
    """
    PURE FUNCTION:
    - No DB
    - No broker
    - No side effects
    """

    if not isinstance(decision, AutoPickDecision):
        raise ValueError("auto_pick_decision_required")

    if not isinstance(risk, RiskSizingDecision):
        raise ValueError("risk_sizing_required")

    return BinanceIntentDraft(
        symbol=decision.symbol,
        side=decision.side,
        expected_qty=risk.expected_qty,
        entry_price=risk.entry_price,
        stop_loss=risk.stop_loss,
        take_profit=risk.take_profit,
        risk_pct=risk.risk_pct,
        risk_abs=risk.risk_abs,
        risk_usdt=risk.risk_usdt,
        reward_risk_ratio=risk.reward_risk_ratio,
        entry_price_reference=risk.entry_price,
        auto_pick_trace={
            "final_score": decision.final_score,
            "decision_reason": decision.decision_reason,
            "evidence": decision.evidence,
        },
    )
