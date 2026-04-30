from __future__ import annotations

import pytest

import apps.api.app.services.risk_to_intent as module
from apps.api.app.services.auto_pick.contracts import AutoPickDecision
from apps.api.app.services.risk.contracts import RiskSizingDecision
from apps.api.app.services.risk_to_intent import build_binance_intent_from_risk


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


def test_build_binance_intent_from_risk_calls_adapter_with_exact_payload(monkeypatch):
    captured = {}

    def fake_create_binance_intent(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "kwargs": kwargs}

    monkeypatch.setattr(module, "create_binance_intent", fake_create_binance_intent)

    result = build_binance_intent_from_risk(
        decision=_decision(),
        risk=_risk(),
    )

    assert result["ok"] is True
    assert captured == {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "expected_qty": 1.0,
        "entry_price": 100.0,
        "stop_loss": 99.0,
        "take_profit": 102.0,
        "auto_pick_trace": {
            "final_score": 0.9,
            "decision_reason": "test",
            "evidence": {"entry_price_reference": 100.0},
        },
    }


def test_invalid_inputs():
    with pytest.raises(ValueError, match="auto_pick_decision_required"):
        build_binance_intent_from_risk(
            decision=None,
            risk=_risk(),
        )

    with pytest.raises(ValueError, match="risk_sizing_required"):
        build_binance_intent_from_risk(
            decision=_decision(),
            risk=None,
        )
