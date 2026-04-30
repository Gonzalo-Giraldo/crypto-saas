from __future__ import annotations

import pytest

from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.auto_pick_to_risk import build_risk_from_auto_pick_decision
from apps.api.app.services.risk.contracts import RiskSizingDecision


def _decision(entry_price_reference=100.0) -> AutoPickDecision:
    return AutoPickDecision(
        symbol="BTCUSDT",
        side="BUY",
        direction="LONG",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="test_model",
        final_score=0.8,
        decision_reason="test",
        evidence={
            "entry_price_reference": entry_price_reference,
            "entry_price_semantics": "reference_only_not_fill",
        },
    )


def test_build_risk_from_auto_pick_decision_returns_risk_sizing_decision():
    result = build_risk_from_auto_pick_decision(
        decision=_decision(),
        capital_base=1000.0,
        risk_pct=0.01,
        reward_risk_ratio=2.0,
    )

    assert isinstance(result, RiskSizingDecision)
    assert result.entry_price == 100.0
    assert result.expected_qty > 0
    assert result.stop_loss > 0
    assert result.take_profit > 0


def test_build_risk_from_auto_pick_decision_requires_entry_price_reference():
    decision = _decision()
    decision.evidence.clear()

    with pytest.raises(ValueError, match="entry_price_reference_required"):
        build_risk_from_auto_pick_decision(
            decision=decision,
            capital_base=1000.0,
            risk_pct=0.01,
            reward_risk_ratio=2.0,
        )


def test_build_risk_from_auto_pick_decision_rejects_non_positive_entry_price_reference():
    with pytest.raises(ValueError, match="entry_price_reference_must_be_positive"):
        build_risk_from_auto_pick_decision(
            decision=_decision(0),
            capital_base=1000.0,
            risk_pct=0.01,
            reward_risk_ratio=2.0,
        )


def test_build_risk_from_auto_pick_decision_rejects_non_positive_capital_base():
    with pytest.raises(ValueError, match="capital_base_must_be_positive"):
        build_risk_from_auto_pick_decision(
            decision=_decision(),
            capital_base=0,
            risk_pct=0.01,
            reward_risk_ratio=2.0,
        )
