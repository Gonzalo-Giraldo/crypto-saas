from __future__ import annotations

import pytest

from apps.api.app.services.intent_draft import (
    build_binance_intent_draft,
    BinanceIntentDraft,
)
from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.risk.contracts import RiskSizingDecision


def _decision():
    return AutoPickDecision(
        symbol="BTCUSDT",
        side="BUY",
        direction="LONG",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="test",
        final_score=0.9,
        decision_reason="test",
        evidence={"entry_price_reference": 100.0},
    )


def _risk():
    return RiskSizingDecision(
        entry_price=100.0,
        stop_loss=99.0,
        take_profit=102.0,
        risk_pct=1.0,
        risk_abs=1.0,
        expected_qty=1.0,
        evidence={},
    )


def test_build_binance_intent_draft_ok():
    draft = build_binance_intent_draft(
        decision=_decision(),
        risk=_risk(),
    )

    assert isinstance(draft, BinanceIntentDraft)

    assert draft.symbol == "BTCUSDT"
    assert draft.side == "BUY"
    assert draft.expected_qty == 1.0
    assert draft.entry_price == 100.0
    assert draft.stop_loss == 99.0
    assert draft.take_profit == 102.0

    assert draft.auto_pick_trace["final_score"] == 0.9


def test_invalid_inputs():
    with pytest.raises(ValueError):
        build_binance_intent_draft(
            decision=None,
            risk=_risk(),
        )

    with pytest.raises(ValueError):
        build_binance_intent_draft(
            decision=_decision(),
            risk=None,
        )
